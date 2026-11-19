import { useState, useEffect, useRef } from 'react';

/**
 * Abortable non-overlapping polling hook with bounded exponential backoff.
 * Distinguishes transient network interruption from terminal backend job failure
 * (network failure is NEVER reported as job failure).
 */
export function usePolling(pollFn, {
  enabled = false,
  isTerminal = () => false,
  initialDelayMs = 1500,
  maxDelayMs = 10000,
  onData,
  onTerminal,
} = {}) {
  const [data, setData] = useState(null);
  const [networkWarning, setNetworkWarning] = useState(null);
  const [terminalReached, setTerminalReached] = useState(false);

  const pollFnRef = useRef(pollFn);
  const isTerminalRef = useRef(isTerminal);
  const onDataRef = useRef(onData);
  const onTerminalRef = useRef(onTerminal);

  useEffect(() => {
    pollFnRef.current = pollFn;
    isTerminalRef.current = isTerminal;
    onDataRef.current = onData;
    onTerminalRef.current = onTerminal;
  });

  useEffect(() => {
    if (!enabled) return undefined;

    let cancelled = false;
    let timerId = null;
    let activeController = null;
    let delay = initialDelayMs;

    const tick = async () => {
      if (cancelled) return;
      activeController = new AbortController();
      try {
        const result = await pollFnRef.current({ signal: activeController.signal });
        if (cancelled) return;
        setNetworkWarning(null);
        setData(result);
        delay = initialDelayMs;
        onDataRef.current?.(result);
        if (isTerminalRef.current(result)) {
          setTerminalReached(true);
          onTerminalRef.current?.(result);
          return;
        }
        setTerminalReached(false);
      } catch (err) {
        if (cancelled || err?.isAborted) return;
        setNetworkWarning('Network connection interrupted — retrying status check; job may still be running.');
        delay = Math.min(maxDelayMs, Math.round(delay * 1.6));
      }
      if (!cancelled) {
        timerId = setTimeout(tick, delay);
      }
    };

    timerId = setTimeout(tick, 0);

    return () => {
      cancelled = true;
      if (timerId) clearTimeout(timerId);
      if (activeController) activeController.abort();
    };
  }, [enabled, initialDelayMs, maxDelayMs]);

  return {
    data,
    networkWarning: enabled ? networkWarning : null,
    polling: enabled && !terminalReached,
  };
}
