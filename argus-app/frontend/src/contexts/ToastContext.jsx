import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';

const ToastContext = createContext(null);

const MAX_VISIBLE = 3;
let _nextId = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timersRef = useRef({});

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    if (timersRef.current[id]) {
      clearTimeout(timersRef.current[id]);
      delete timersRef.current[id];
    }
  }, []);

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++_nextId;
    setToasts((prev) => {
      const updated = [...prev, { id, message, type }];
      return updated.slice(-MAX_VISIBLE);
    });
    if (duration > 0) {
      timersRef.current[id] = setTimeout(() => removeToast(id), duration);
    }
    return id;
  }, [removeToast]);

  useEffect(() => {
    return () => {
      Object.values(timersRef.current).forEach(clearTimeout);
    };
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
  return ctx;
}
