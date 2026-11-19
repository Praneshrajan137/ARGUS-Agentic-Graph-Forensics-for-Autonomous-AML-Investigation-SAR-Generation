import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getRuntime, getAuthMe, logout as apiLogout, setCsrfToken } from '@/api/client';
import { clearAllQueries } from '@/hooks/useQuery';

const AuthContext = createContext({
  mode: 'research',
  loading: true,
  user: null,
  signOut: async () => {},
  refreshAuth: async () => {},
});

export function AuthProvider({ children }) {
  const [mode, setMode] = useState('research');
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshAuth = useCallback(async () => {
    setLoading(true);
    try {
      const rt = await getRuntime();
      if (rt?.mode === 'production') {
        setMode('production');
        try {
          const me = await getAuthMe();
          setUser(me?.authenticated ? me : null);
        } catch {
          setUser(null);
        }
      } else {
        setMode('research');
        setUser(null);
      }
    } catch {
      // Legacy research backend does not expose /api/runtime
      setMode('research');
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshAuth();
  }, [refreshAuth]);

  const signOut = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // Clear local state regardless of server response
    }
    setCsrfToken(null);
    setUser(null);
    clearAllQueries();
    window.dispatchEvent(new CustomEvent('argus:identity-change'));
  }, []);

  return (
    <AuthContext.Provider value={{ mode, loading, user, signOut, refreshAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
