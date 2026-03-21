import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shuffle,
  Loader2,
  AlertTriangle,
  Server,
  Zap,
  Database,
} from 'lucide-react';
import PageHeader from '@/components/shared/PageHeader';
import GlowCard from '@/components/shared/GlowCard';
import ErrorCard from '@/components/shared/ErrorCard';
import { useQuery, invalidateQueries } from '@/hooks/useQuery';
import { getConfig, getHealth, generateWorld, resetState, getAgentConfig, getAgentCard } from '@/api/client';
import { useToast } from '@/contexts/ToastContext';

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] },
  },
};

const DIFFICULTY_LABELS = {
  1: 'Trivial',
  2: 'Easy',
  3: 'Simple',
  4: 'Moderate',
  5: 'Standard',
  6: 'Challenging',
  7: 'Hard',
  8: 'Very Hard',
  9: 'Extreme',
  10: 'Expert',
};

export default function Settings() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const { data: config } = useQuery('config', getConfig);
  const { data: health } = useQuery('health-settings', getHealth);
  const { data: agentConfig } = useQuery('agent-config', getAgentConfig);
  const { data: agentCard } = useQuery('agent-card', getAgentCard);

  // Generate form state
  const [seed, setSeed] = useState(42);
  const [difficulty, setDifficulty] = useState(5);
  const [nodeCount, setNodeCount] = useState(1000);
  const [generating, setGenerating] = useState(false);
  const [generatePhase, setGeneratePhase] = useState('');
  const [generateError, setGenerateError] = useState(null);

  // Reset state
  const [resetting, setResetting] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const handleGenerate = async () => {
    setGenerating(true);
    setGenerateError(null);
    setGeneratePhase('Constructing financial network...');

    try {
      // Simulate phased progress (backend is synchronous)
      const phases = [
        'Constructing financial network...',
        'Injecting crime patterns...',
        'Generating evidence documents...',
        'Building ground truth...',
      ];
      let phaseIdx = 0;
      const interval = setInterval(() => {
        phaseIdx = Math.min(phaseIdx + 1, phases.length - 1);
        setGeneratePhase(phases[phaseIdx]);
      }, 1500);

      await generateWorld({ seed, difficulty, node_count: nodeCount });

      clearInterval(interval);
      setGeneratePhase('Complete!');
      addToast(`Financial world generated — seed ${seed}, ${nodeCount} nodes`, 'success');

      // Invalidate all cached queries
      invalidateQueries('');

      // Redirect to dashboard after brief delay
      setTimeout(() => {
        setGenerating(false);
        navigate('/');
      }, 800);
    } catch (err) {
      setGenerating(false);
      setGenerateError(err);
      addToast(`Generation failed: ${err.message}`, 'error');
    }
  };

  const handleReset = async () => {
    setResetting(true);
    try {
      await resetState();
      invalidateQueries('');
      addToast('All data has been reset.', 'warning');
      setShowResetConfirm(false);
      navigate('/');
    } catch (err) {
      setGenerateError(err);
      addToast(`Reset failed: ${err.message}`, 'error');
    } finally {
      setResetting(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Dataset generation, system info, and configuration"
      />

      <motion.div
        variants={stagger}
        initial="hidden"
        animate="show"
        className="space-y-6"
      >
        {/* ═══ GENERATE NEW DATASET ═══ */}
        <motion.div variants={fadeUp}>
          <GlowCard className="p-6">
            <div className="flex items-center gap-2 mb-5">
              <Database className="w-5 h-5 text-accent" />
              <h2 className="font-display text-xl text-text-0">
                Generate New Dataset
              </h2>
            </div>

            <div className="grid grid-cols-3 gap-6">
              {/* Seed */}
              <div>
                <label className="text-sm font-medium text-text-1 mb-1.5 block">
                  Random Seed
                </label>
                <div className="flex gap-2">
                  <input
                    data-testid="seed-input"
                    type="number"
                    value={seed}
                    onChange={(e) => setSeed(+e.target.value)}
                    className="flex-1 px-3 py-2.5 text-sm font-mono bg-surface-0 border border-surface-3
                               rounded-btn focus:outline-none focus:ring-2 focus:ring-accent/30"
                  />
                  <button
                    data-testid="random-seed-btn"
                    onClick={() =>
                      setSeed(Math.floor(Math.random() * 10000))
                    }
                    className="px-3 py-2.5 bg-surface-1 border border-surface-3 rounded-btn
                               hover:bg-surface-2 transition-colors"
                    title="Random seed"
                  >
                    <Shuffle className="w-4 h-4 text-text-2" />
                  </button>
                </div>
              </div>

              {/* Difficulty */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-sm font-medium text-text-1">
                    Difficulty
                  </label>
                  <span className="font-mono text-sm font-bold text-accent">
                    {difficulty} — {DIFFICULTY_LABELS[difficulty]}
                  </span>
                </div>
                <input
                  data-testid="difficulty-slider"
                  type="range"
                  min={1}
                  max={10}
                  value={difficulty}
                  onChange={(e) => setDifficulty(+e.target.value)}
                  className="w-full h-2 bg-surface-2 rounded-full appearance-none cursor-pointer
                             [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5
                             [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full
                             [&::-webkit-slider-thumb]:bg-accent [&::-webkit-slider-thumb]:shadow-md
                             [&::-webkit-slider-thumb]:cursor-pointer"
                />
                <div className="flex justify-between text-[10px] font-mono text-text-3 mt-1">
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                    <span
                      key={n}
                      className={
                        difficulty === n ? 'text-accent font-bold' : ''
                      }
                    >
                      {n}
                    </span>
                  ))}
                </div>
              </div>

              {/* Node Count */}
              <div>
                <label className="text-sm font-medium text-text-1 mb-1.5 block">
                  Node Count
                </label>
                <input
                  data-testid="node-count-input"
                  type="number"
                  value={nodeCount}
                  onChange={(e) =>
                    setNodeCount(
                      Math.max(50, Math.min(5000, +e.target.value))
                    )
                  }
                  min={50}
                  max={5000}
                  step={50}
                  className="w-full px-3 py-2.5 text-sm font-mono bg-surface-0 border border-surface-3
                             rounded-btn focus:outline-none focus:ring-2 focus:ring-accent/30"
                />
                <p className="text-[10px] text-text-3 mt-1">
                  Range: 50–5,000 entities
                </p>
              </div>
            </div>

            <button
              data-testid="generate-btn"
              onClick={handleGenerate}
              disabled={generating}
              className="mt-6 w-full py-3 bg-accent text-white font-semibold rounded-btn
                         hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed
                         transition-all shadow-sm flex items-center justify-center gap-2"
            >
              {generating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {generatePhase}
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" /> Generate Financial World
                </>
              )}
            </button>

            {generateError && (
              <div className="mt-4">
                <ErrorCard error={generateError} onRetry={handleGenerate} />
              </div>
            )}
          </GlowCard>
        </motion.div>

        {/* ═══ SYSTEM INFORMATION ═══ */}
        <motion.div variants={fadeUp}>
          <GlowCard className="p-6">
            <div className="flex items-center gap-2 mb-5">
              <Server className="w-5 h-5 text-accent" />
              <h2 className="font-display text-xl text-text-0">
                System Information
              </h2>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {[
                {
                  label: 'FORGE Agent',
                  value: health?.forge_version || '—',
                },
                {
                  label: 'TRACER Agent',
                  value: health?.tracer_version || '—',
                },
                {
                  label: 'Unified Backend',
                  value: health?.unified_version || '—',
                },
                { label: 'Status', value: health?.status || '—' },
                {
                  label: 'Node Count',
                  value:
                    health?.node_count?.toLocaleString() || '—',
                },
                {
                  label: 'Edge Count',
                  value:
                    health?.edge_count?.toLocaleString() || '—',
                },
                {
                  label: 'Uptime',
                  value: health?.uptime_seconds
                    ? `${Math.round(health.uptime_seconds)}s`
                    : '—',
                },
                {
                  label: 'Graph Loaded',
                  value: health?.graph_loaded ? 'Yes' : 'No',
                },
              ].map(({ label, value }) => (
                <div
                  key={label}
                  className="flex items-center justify-between py-2.5 px-4 bg-surface-1 rounded-lg"
                >
                  <span className="text-sm text-text-2">{label}</span>
                  <span className="font-mono text-sm font-bold text-text-0">
                    {value}
                  </span>
                </div>
              ))}
            </div>
          </GlowCard>
        </motion.div>

        {/* ═══ PURPLE AGENT CONFIG ═══ */}
        {agentConfig && (
          <motion.div variants={fadeUp}>
            <GlowCard className="p-6">
              <div className="flex items-center gap-2 mb-5">
                <Zap className="w-5 h-5 text-accent" />
                <h2 className="font-display text-xl text-text-0">
                  Purple Agent Configuration
                </h2>
                {agentCard && (
                  <span className="ml-auto text-xs font-mono text-text-3">
                    {agentCard.name} v{agentConfig.AGENT_VERSION || '7.0.0'}
                  </span>
                )}
              </div>

              {agentCard && (
                <div className="mb-4 p-3 bg-surface-1 rounded-lg">
                  <p className="text-sm text-text-1">{agentCard.description}</p>
                  <div className="flex gap-4 mt-2 text-xs text-text-3">
                    <span>Mode: {agentCard.communication?.mode || 'unified'}</span>
                    <span>Protocol: {agentCard.communication?.protocol || 'A2A'}</span>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto">
                {Object.entries(agentConfig)
                  .filter(([k]) => !k.startsWith('_'))
                  .map(([key, value]) => (
                    <div
                      key={key}
                      className="flex items-center justify-between py-2 px-3 bg-surface-1 rounded-lg text-xs"
                    >
                      <span className="text-text-2 font-mono truncate mr-2">{key}</span>
                      <span className="font-mono font-bold text-text-0 truncate max-w-[50%] text-right">
                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                      </span>
                    </div>
                  ))}
              </div>
            </GlowCard>
          </motion.div>
        )}

        {/* ═══ DANGER ZONE ═══ */}
        <motion.div variants={fadeUp}>
          <div className="bg-surface-0 rounded-card border-2 border-rose-200 p-6">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-5 h-5 text-status-rose" />
              <h2 className="font-display text-xl text-status-rose">
                Danger Zone
              </h2>
            </div>
            <p className="text-sm text-text-2 mb-4">
              Resetting will clear all in-memory data: the graph, all
              investigations, evidence documents, and assessment results.
              This action cannot be undone.
            </p>

            <AnimatePresence mode="wait">
              {!showResetConfirm ? (
                <motion.div
                  key="reset-btn"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <button
                    data-testid="reset-btn"
                    onClick={() => setShowResetConfirm(true)}
                    className="px-5 py-2.5 bg-rose-50 text-status-rose text-sm font-semibold rounded-btn
                               border border-rose-200 hover:bg-rose-100 transition-colors"
                  >
                    Reset All Data
                  </button>
                </motion.div>
              ) : (
                <motion.div
                  key="confirm"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  className="flex items-center gap-3 p-4 bg-rose-50 rounded-lg border border-rose-200"
                >
                  <span className="text-sm text-rose-800 font-medium">
                    Are you sure? This will destroy all data.
                  </span>
                  <button
                    data-testid="confirm-reset-btn"
                    onClick={handleReset}
                    disabled={resetting}
                    className="px-4 py-2 bg-rose-600 text-white text-sm font-bold rounded-btn
                               hover:bg-rose-700 disabled:opacity-50 transition-colors"
                  >
                    {resetting ? 'Resetting...' : 'Yes, Reset Everything'}
                  </button>
                  <button
                    data-testid="cancel-reset-btn"
                    onClick={() => setShowResetConfirm(false)}
                    className="px-4 py-2 bg-surface-0 text-text-1 text-sm font-medium rounded-btn
                               border border-surface-3 hover:bg-surface-1 transition-colors"
                  >
                    Cancel
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}
