import { useState } from 'react';
import { motion } from 'framer-motion';
import { Zap, Shuffle, Play, FlaskConical, Gauge, Microscope } from 'lucide-react';
import GlowCard from '@/components/shared/GlowCard';

const DIFFICULTY_LABELS = {
  1: 'Trivial', 2: 'Easy', 3: 'Simple', 4: 'Moderate', 5: 'Standard',
  6: 'Challenging', 7: 'Hard', 8: 'Very Hard', 9: 'Extreme', 10: 'Expert',
};

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] } },
};

export default function BenchmarkConfig({ onRun, isRunning, graphLoaded }) {
  const [mode, setMode] = useState('fast');
  const [nodeCount, setNodeCount] = useState(1000);
  const [difficulty, setDifficulty] = useState(5);
  const [seed, setSeed] = useState(42);
  const [hopDepth, setHopDepth] = useState(3);
  const [jurisdiction, setJurisdiction] = useState('fincen');

  const handleRandomSeed = () => setSeed(Math.floor(Math.random() * 2147483647));

  const handleSubmit = (generate) => {
    onRun({
      mode,
      generate,
      node_count: nodeCount,
      difficulty,
      seed,
      hop_depth: hopDepth,
      jurisdiction,
    });
  };

  return (
    <motion.div variants={fadeUp} className="space-y-6">
      <GlowCard className="p-8" accent>
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-lg bg-accent flex items-center justify-center">
            <FlaskConical className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-display text-text-0">Benchmark Configuration</h2>
            <p className="text-sm text-text-2">
              Investigate every node in the graph and measure detection accuracy
            </p>
          </div>
        </div>

        {/* Mode Toggle */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-text-1 mb-2">Benchmark Mode</label>
          <div className="flex gap-2">
            {[
              { value: 'fast', label: 'Fast Sweep', desc: '~30s', icon: Gauge },
              { value: 'full', label: 'Full Pipeline', desc: '~50min', icon: Microscope },
            ].map(({ value, label, desc, icon: Icon }) => (
              <button
                key={value}
                onClick={() => setMode(value)}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-btn text-sm font-medium transition-all ${
                  mode === value
                    ? 'bg-accent text-white shadow-sm'
                    : 'bg-surface-2 text-text-2 hover:text-text-0 hover:bg-surface-3'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{label}</span>
                <span className={`text-xs ${mode === value ? 'text-white/70' : 'text-text-3'}`}>({desc})</span>
              </button>
            ))}
          </div>
          <p className="text-xs text-text-3 mt-1.5">
            {mode === 'fast'
              ? 'Runs structuring & layering detection heuristics directly on every node. No SAR generation or assessment.'
              : 'Full 8-step investigation pipeline + assessment per node. Includes SAR generation and entity-level metrics.'}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Node Count */}
          <div>
            <label className="block text-sm font-medium text-text-1 mb-2">Graph Size</label>
            <div className="flex gap-2">
              {[1000, 2000, 5000].map((n) => (
                <button
                  key={n}
                  onClick={() => setNodeCount(n)}
                  className={`flex-1 px-4 py-2.5 rounded-btn text-sm font-medium transition-all ${
                    nodeCount === n
                      ? 'bg-accent text-white shadow-sm'
                      : 'bg-surface-2 text-text-2 hover:text-text-0 hover:bg-surface-3'
                  }`}
                >
                  {n.toLocaleString()} nodes
                </button>
              ))}
            </div>
          </div>

          {/* Seed */}
          <div>
            <label className="block text-sm font-medium text-text-1 mb-2">Random Seed</label>
            <div className="flex gap-2">
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(parseInt(e.target.value) || 0)}
                min={0}
                max={2147483647}
                className="flex-1 px-3 py-2.5 rounded-btn bg-surface-1 border border-surface-3 text-text-0 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
              />
              <button
                onClick={handleRandomSeed}
                className="px-3 py-2.5 rounded-btn bg-surface-2 text-text-2 hover:text-text-0 hover:bg-surface-3 transition-all"
                title="Randomize seed"
              >
                <Shuffle className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Difficulty */}
          <div>
            <label className="block text-sm font-medium text-text-1 mb-2">
              Difficulty: <span className="text-accent">{difficulty} — {DIFFICULTY_LABELS[difficulty]}</span>
            </label>
            <input
              type="range"
              min={1}
              max={10}
              value={difficulty}
              onChange={(e) => setDifficulty(parseInt(e.target.value))}
              className="w-full accent-[var(--accent-base)]"
            />
            <div className="flex justify-between text-xs text-text-3 mt-1">
              <span>1 Trivial</span>
              <span>10 Expert</span>
            </div>
          </div>

          {/* Hop Depth */}
          <div>
            <label className="block text-sm font-medium text-text-1 mb-2">
              Analysis Depth: <span className="text-accent">{hopDepth} hops</span>
            </label>
            <input
              type="range"
              min={1}
              max={10}
              value={hopDepth}
              onChange={(e) => setHopDepth(parseInt(e.target.value))}
              className="w-full accent-[var(--accent-base)]"
            />
            <div className="flex justify-between text-xs text-text-3 mt-1">
              <span>1 hop</span>
              <span>10 hops</span>
            </div>
          </div>

          {/* Jurisdiction */}
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-text-1 mb-2">Jurisdiction</label>
            <div className="flex gap-2">
              {[
                { value: 'fincen', label: 'FinCEN (US/BSA)', flag: '\u{1F1FA}\u{1F1F8}' },
                { value: 'fiu_ind', label: 'FIU-IND (India/PMLA)', flag: '\u{1F1EE}\u{1F1F3}' },
              ].map(({ value, label, flag }) => (
                <button
                  key={value}
                  onClick={() => setJurisdiction(value)}
                  className={`flex-1 px-4 py-2.5 rounded-btn text-sm font-medium transition-all ${
                    jurisdiction === value
                      ? 'bg-accent text-white shadow-sm'
                      : 'bg-surface-2 text-text-2 hover:text-text-0 hover:bg-surface-3'
                  }`}
                >
                  {flag} {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 mt-8">
          <button
            onClick={() => handleSubmit(true)}
            disabled={isRunning}
            className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-btn bg-accent text-white font-medium text-sm hover:bg-accent-hover transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            <Zap className="w-4 h-4" />
            Generate & Run Benchmark
          </button>
          {graphLoaded && (
            <button
              onClick={() => handleSubmit(false)}
              disabled={isRunning}
              className="flex items-center justify-center gap-2 px-6 py-3 rounded-btn bg-surface-2 text-text-1 font-medium text-sm hover:bg-surface-3 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="w-4 h-4" />
              Run on Current Graph
            </button>
          )}
        </div>

        <p className="text-xs text-text-3 mt-3">
          {mode === 'fast'
            ? `Fast sweep across all ${nodeCount.toLocaleString()} nodes using detection heuristics only. Estimated time: ${nodeCount <= 1000 ? '~30 seconds' : nodeCount <= 2000 ? '~1 minute' : '~2-3 minutes'}.`
            : `Full pipeline investigation of all ${nodeCount.toLocaleString()} nodes with SAR generation & assessment. Estimated time: ${nodeCount <= 1000 ? '~50 minutes' : '~2-4 hours'}.`}
        </p>
      </GlowCard>
    </motion.div>
  );
}
