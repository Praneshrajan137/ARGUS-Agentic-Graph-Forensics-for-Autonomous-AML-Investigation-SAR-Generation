import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { invalidateQueries } from '@/hooks/useQuery';
import { useToast } from '@/contexts/ToastContext';

/**
 * Invisible component that detects backend epoch changes (generate/reset)
 * and invalidates the frontend query cache.
 *
 * Mount once inside ToastProvider and BrowserRouter.
 */
export default function StaleStateGuard() {
  const navigate = useNavigate();
  const { addToast } = useToast();

  useEffect(() => {
    function handleEpochChange() {
      invalidateQueries('');
      addToast('Backend data refreshed — reloading from Dashboard.', 'info', 5000);
      setTimeout(() => navigate('/', { replace: true }), 300);
    }

    window.addEventListener('argus:epoch-change', handleEpochChange);
    return () => window.removeEventListener('argus:epoch-change', handleEpochChange);
  }, [addToast, navigate]);

  return null;
}
