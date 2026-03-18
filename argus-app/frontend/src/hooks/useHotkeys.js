import { useEffect, useRef } from 'react';

/**
 * Global keyboard shortcut hook.
 *
 * @param {Array<{ key: string, ctrl?: boolean, handler: Function }>} shortcuts
 *   - key: the `e.key` value to match (e.g. '?', 'Escape', '1')
 *   - ctrl: if true, requires Ctrl/Cmd modifier
 *   - handler: callback to invoke
 *
 * Shortcuts are ignored when an input/textarea/select/contentEditable is focused,
 * EXCEPT for 'Escape' which always fires.
 */
export function useHotkeys(shortcuts) {
  const ref = useRef(shortcuts);
  ref.current = shortcuts;

  useEffect(() => {
    function onKeyDown(e) {
      const tag = e.target.tagName;
      const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable;

      for (const s of ref.current) {
        if (e.key !== s.key) continue;
        if (s.ctrl && !(e.ctrlKey || e.metaKey)) continue;
        if (!s.ctrl && (e.ctrlKey || e.metaKey)) continue;

        // Allow Escape even when typing; block other shortcuts in inputs
        if (isInput && e.key !== 'Escape') continue;

        e.preventDefault();
        s.handler();
        return;
      }
    }

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, []);
}
