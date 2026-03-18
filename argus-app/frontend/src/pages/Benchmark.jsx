import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Zap } from 'lucide-react';
import { useQuery } from '@/hooks/useQuery';
import { getHealth, runBenchmark, getBenchmark } from '@/api/client';
import PageHeader from '@/components/shared/PageHeader';
import ErrorCard from '@/components/shared/ErrorCard';
import BenchmarkConfig from '@/components/benchmark/BenchmarkConfig';
import BenchmarkProgress from '@/components/benchmark/BenchmarkProgress';
import BenchmarkResults from '@/components/benchmark/BenchmarkResults';

const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.08 } } };

export default function Benchmark() {
  const { data: health } = useQuery('health', getHealth, { staleTime: 10000 });

  // Page states: 'config' | 'running' | 'complete'
  const [phase, setPhase] = useState('config');
  const [benchmarkId, setBenchmarkId] = useState(null);
  const [benchmark, setBenchmark] = useState(null);
  const [error, setError] = useState(null);

  const handleRun = async (config) => {
    setError(null);
    setPhase('running');
    try {
      const result = await runBenchmark(config);
      setBenchmarkId(result.benchmark_id);
    } catch (err) {
      setError(err);
      setPhase('config');
    }
  };

  const handleComplete = useCallback(async (status) => {
    if (status === 'COMPLETE') {
      try {
        const data = await getBenchmark(benchmarkId);
        setBenchmark(data);
        setPhase('complete');
      } catch (err) {
        setError(err);
        setPhase('config');
      }
    } else {
      setError(new Error('Benchmark failed. Check backend logs.'));
      setPhase('config');
    }
  }, [benchmarkId]);

  const handleReset = () => {
    setPhase('config');
    setBenchmarkId(null);
    setBenchmark(null);
    setError(null);
  };

  return (
    <div>
      <PageHeader
        title="Benchmark"
        subtitle="Run all-node investigations and measure detection accuracy against ground truth"
      >
        {phase === 'complete' && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-badge bg-emerald-100 text-emerald-700 text-xs font-medium">
            <Zap className="w-3 h-3" />
            Benchmark Complete
          </div>
        )}
      </PageHeader>

      <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">
        {error && (
          <ErrorCard error={error} onRetry={handleReset} />
        )}

        {phase === 'config' && (
          <BenchmarkConfig
            onRun={handleRun}
            isRunning={false}
            graphLoaded={health?.graph_loaded}
          />
        )}

        {phase === 'running' && benchmarkId && (
          <BenchmarkProgress
            benchmarkId={benchmarkId}
            onComplete={handleComplete}
          />
        )}

        {phase === 'complete' && benchmark && (
          <BenchmarkResults
            benchmark={benchmark}
            onReset={handleReset}
          />
        )}
      </motion.div>
    </div>
  );
}
