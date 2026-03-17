import { useState, useEffect, useRef, useCallback } from 'react';

// Simple in-memory cache with staleness
const cache = new Map();
const inflight = new Map();

/**
 * Data fetching hook with deduplication and stale-while-revalidate.
 *
 * @param {string} key - Cache key (usually the API path)
 * @param {Function} fetcher - Async function that returns data
 * @param {Object} options - { enabled, staleTime, onSuccess, onError }
 */
export function useQuery(key, fetcher, options = {}) {
  const { enabled = true, staleTime = 30000, onSuccess, onError } = options;
  const [data, setData] = useState(() => cache.get(key)?.data ?? null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(!cache.has(key));
  const mountedRef = useRef(true);

  const execute = useCallback(async () => {
    if (!enabled) return;

    // Check cache freshness
    const cached = cache.get(key);
    if (cached && Date.now() - cached.timestamp < staleTime) {
      setData(cached.data);
      setLoading(false);
      return;
    }

    // Deduplicate inflight requests
    if (inflight.has(key)) {
      try {
        const result = await inflight.get(key);
        if (mountedRef.current) {
          setData(result);
          setLoading(false);
        }
      } catch (err) {
        if (mountedRef.current) {
          setError(err);
          setLoading(false);
        }
      }
      return;
    }

    setLoading(true);
    setError(null);

    const promise = fetcher();
    inflight.set(key, promise);

    try {
      const result = await promise;
      cache.set(key, { data: result, timestamp: Date.now() });
      if (mountedRef.current) {
        setData(result);
        setLoading(false);
        onSuccess?.(result);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
        setLoading(false);
        onError?.(err);
      }
    } finally {
      inflight.delete(key);
    }
  }, [key, fetcher, enabled, staleTime, onSuccess, onError]);

  useEffect(() => {
    mountedRef.current = true;
    execute();
    return () => { mountedRef.current = false; };
  }, [execute]);

  const refetch = useCallback(() => {
    cache.delete(key);
    return execute();
  }, [key, execute]);

  return { data, error, loading, refetch };
}

/** Invalidate cache entries matching a prefix. */
export function invalidateQueries(prefix) {
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) cache.delete(key);
  }
}
