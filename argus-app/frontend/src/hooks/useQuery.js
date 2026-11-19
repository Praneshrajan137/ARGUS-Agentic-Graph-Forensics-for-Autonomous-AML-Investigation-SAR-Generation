import { useState, useEffect, useRef, useCallback } from 'react';

const cache = new Map();
const controllers = new Set();
let scopeGeneration = 0;

/**
 * Race-safe, abortable data fetching hook.
 * - Passes an AbortSignal into the fetcher and cancels stale requests on key change/unmount.
 * - Uses a monotonic request sequence + scope generation so a prior case response can NEVER
 *   overwrite a newly selected case or post-sign-out state.
 * - Clears all cached entries and aborts in-flight work on identity/scope changes.
 */
export function useQuery(key, fetcher, options = {}) {
  const { enabled = true, staleTime = 30000, onSuccess, onError } = options;
  const [data, setData] = useState(() => (key && cache.has(key) ? cache.get(key).data : null));
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(() => Boolean(enabled && key && !cache.has(key)));

  const seqRef = useRef(0);
  const activeKeyRef = useRef(key);
  const fetcherRef = useRef(fetcher);
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    fetcherRef.current = fetcher;
    onSuccessRef.current = onSuccess;
    onErrorRef.current = onError;
  });

  const execute = useCallback(async ({ force = false } = {}) => {
    if (!enabled || !key) {
      setLoading(false);
      return;
    }

    const cached = cache.get(key);
    if (!force && cached && Date.now() - cached.timestamp < staleTime) {
      setData(cached.data);
      setError(null);
      setLoading(false);
      return;
    }

    const requestSeq = ++seqRef.current;
    const myScope = scopeGeneration;
    activeKeyRef.current = key;

    const controller = new AbortController();
    controllers.add(controller);

    setLoading(true);
    setError(null);

    try {
      const result = await fetcherRef.current({ signal: controller.signal });
      if (controller.signal.aborted || myScope !== scopeGeneration || seqRef.current !== requestSeq || activeKeyRef.current !== key) {
        return;
      }
      cache.set(key, { data: result, timestamp: Date.now() });
      setData(result);
      setLoading(false);
      onSuccessRef.current?.(result);
    } catch (err) {
      if (controller.signal.aborted || err?.isAborted || myScope !== scopeGeneration || seqRef.current !== requestSeq || activeKeyRef.current !== key) {
        return;
      }
      setError(err);
      setLoading(false);
      onErrorRef.current?.(err);
    } finally {
      controllers.delete(controller);
    }
  }, [key, enabled, staleTime]);

  useEffect(() => {
    activeKeyRef.current = key;
    if (!enabled || !key) {
      setData(null);
      setError(null);
      setLoading(false);
      return undefined;
    }
    const cached = cache.get(key);
    setData(cached ? cached.data : null);
    setError(null);

    const requestSeq = ++seqRef.current;
    const myScope = scopeGeneration;
    if (cached && Date.now() - cached.timestamp < staleTime) {
      setLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    controllers.add(controller);
    setLoading(true);

    (async () => {
      try {
        const result = await fetcherRef.current({ signal: controller.signal });
        if (controller.signal.aborted || myScope !== scopeGeneration || seqRef.current !== requestSeq) {
          return;
        }
        cache.set(key, { data: result, timestamp: Date.now() });
        setData(result);
        setLoading(false);
        onSuccessRef.current?.(result);
      } catch (err) {
        if (controller.signal.aborted || err?.isAborted || myScope !== scopeGeneration || seqRef.current !== requestSeq) {
          return;
        }
        setError(err);
        setLoading(false);
        onErrorRef.current?.(err);
      } finally {
        controllers.delete(controller);
      }
    })();

    return () => {
      controller.abort();
      controllers.delete(controller);
    };
  }, [key, enabled, staleTime]);

  useEffect(() => {
    const onScopeReset = () => {
      seqRef.current += 1;
      setData(null);
      setError(null);
      setLoading(false);
    };
    window.addEventListener('argus:identity-change', onScopeReset);
    window.addEventListener('argus:scope-change', onScopeReset);
    return () => {
      window.removeEventListener('argus:identity-change', onScopeReset);
      window.removeEventListener('argus:scope-change', onScopeReset);
    };
  }, []);

  const refetch = useCallback(() => {
    if (key) cache.delete(key);
    return execute({ force: true });
  }, [key, execute]);

  return { data, error, loading, refetch };
}

/** Invalidate cache entries matching a prefix. */
export function invalidateQueries(prefix = '') {
  for (const k of cache.keys()) {
    if (k.startsWith(prefix)) cache.delete(k);
  }
}

/** Clear all cached queries and abort every in-flight fetch (called on identity/scope change). */
export function clearAllQueries() {
  scopeGeneration += 1;
  cache.clear();
  for (const ctrl of controllers) {
    ctrl.abort();
  }
  controllers.clear();
}
