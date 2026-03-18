import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';
import GlowCard from '@/components/shared/GlowCard';
import { getBenchmarkProgress } from '@/api/client';

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] } },
};

function formatDuration(ms) {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (minutes > 0) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}

export default function BenchmarkProgress({ benchmarkId, onComplete }) {
  const [progress, setProgress] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const startTime = useRef(Date.now());
  const intervalRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!benchmarkId) return;

    // Poll progress every 1.5 seconds
    const poll = async () => {
      try {
        const data = await getBenchmarkProgress(benchmarkId);
        setProgress(data);
        if (data.status === 'COMPLETE' || data.status === 'FAILED') {
          clearInterval(intervalRef.current);
          clearInterval(timerRef.current);
          onComplete(data.status);
        }
      } catch {
        // Retry silently
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 1500);

    // Elapsed time counter
    timerRef.current = setInterval(() => {
      setElapsed(Date.now() - startTime.current);
    }, 1000);

    return () => {
      clearInterval(intervalRef.current);
      clearInterval(timerRef.current);
    };
  }, [benchmarkId, onComplete]);

  const pct = progress?.progress || 0;
  const completed = progress?.completed_count || 0;
  const total = progress?.total_count || 0;
  const currentNode = progress?.current_node || '...';
  const status = progress?.status || 'RUNNING';

  // Estimate remaining time
  const avgPerNode = completed > 0 ? elapsed / completed : 0;
  const remaining = avgPerNode * (total - completed);

  return (
    <motion.div variants={fadeUp} className="space-y-6">
      <GlowCard className="p-8" accent>
        <div className="flex items-center gap-3 mb-6">
          {status === 'RUNNING' ? (
            <Loader2 className="w-6 h-6 text-accent animate-spin" />
          ) : status === 'COMPLETE' ? (
            <CheckCircle2 className="w-6 h-6 text-emerald-500" />
          ) : (
            <XCircle className="w-6 h-6 text-rose-500" />
          )}
          <div>
            <h2 className="text-lg font-display text-text-0">
              {status === 'RUNNING' ? 'Benchmark Running' : status === 'COMPLETE' ? 'Benchmark Complete' : 'Benchmark Failed'}
            </h2>
            <p className="text-sm text-text-2">
              {status === 'RUNNING'
                ? `Investigating node ${currentNode} (${completed} of ${total})`
                : `Processed ${completed} of ${total} nodes`}
            </p>
          </div>
        </div>

        {/* Progress bar */}
        <div className="relative w-full h-4 bg-surface-2 rounded-full overflow-hidden mb-4">
          <motion.div
            className="absolute inset-y-0 left-0 bg-accent rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          />
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-[10px] font-mono font-bold text-text-0 drop-shadow-sm">
              {pct.toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-2xl font-mono font-bold text-text-0">{completed}</div>
            <div className="text-xs text-text-3">Completed</div>
          </div>
          <div>
            <div className="text-2xl font-mono font-bold text-text-0">{total}</div>
            <div className="text-xs text-text-3">Total Nodes</div>
          </div>
          <div>
            <div className="text-2xl font-mono font-bold text-text-0">{formatDuration(elapsed)}</div>
            <div className="text-xs text-text-3">Elapsed</div>
          </div>
          <div>
            <div className="text-2xl font-mono font-bold text-text-0">
              {completed > 0 && status === 'RUNNING' ? formatDuration(remaining) : '--'}
            </div>
            <div className="text-xs text-text-3">Remaining</div>
          </div>
        </div>

        {/* Live ticker */}
        {status === 'RUNNING' && completed > 0 && (
          <div className="mt-4 px-3 py-2 bg-surface-1 rounded-badge border border-surface-3">
            <span className="text-xs font-mono text-text-2">
              Avg {(elapsed / completed / 1000).toFixed(2)}s/node
              {' \u00B7 '}
              {(completed / (elapsed / 1000)).toFixed(1)} nodes/sec
            </span>
          </div>
        )}
      </GlowCard>
    </motion.div>
  );
}
