import { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Target, ShieldAlert, Activity, Clock,
  ChevronUp, ChevronDown, CheckCircle2, XCircle,
  RotateCcw,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import GlowCard from '@/components/shared/GlowCard';
import StatCard from '@/components/shared/StatCard';
import ScoreGauge from '@/components/assessment/ScoreGauge';

const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.08 } } };
const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] } },
};

const PAGE_SIZE = 50;

function formatMs(ms) {
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.round(s % 60)}s`;
}

function ScoreDistributionChart({ nodeResults }) {
  const buckets = useMemo(() => {
    const b = Array.from({ length: 10 }, (_, i) => ({
      range: `${i * 10}-${(i + 1) * 10}`,
      count: 0,
      label: `${i * 10}%`,
    }));
    for (const r of nodeResults) {
      const idx = Math.min(Math.floor(r.assessment_score / 10), 9);
      b[idx].count++;
    }
    return b;
  }, [nodeResults]);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={buckets} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'var(--text-3)' }} />
        <YAxis tick={{ fontSize: 11, fill: 'var(--text-3)' }} />
        <Tooltip
          contentStyle={{
            background: 'var(--surface-0)',
            border: '1px solid var(--surface-3)',
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {buckets.map((_, i) => (
            <Cell key={i} fill={i >= 8 ? 'var(--emerald-base)' : i >= 6 ? 'var(--accent-base)' : i >= 3 ? 'var(--amber-base)' : 'var(--rose-base)'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function ResultsTable({ nodeResults }) {
  const [sortKey, setSortKey] = useState('node_id');
  const [sortAsc, setSortAsc] = useState(true);
  const [page, setPage] = useState(0);
  const [filterCrime, setFilterCrime] = useState('all'); // all, crime, clean, incorrect

  const filtered = useMemo(() => {
    let data = [...nodeResults];
    if (filterCrime === 'crime') data = data.filter((r) => r.is_crime_node);
    else if (filterCrime === 'clean') data = data.filter((r) => !r.is_crime_node);
    else if (filterCrime === 'incorrect') data = data.filter((r) => !r.correct);
    return data;
  }, [nodeResults, filterCrime]);

  const sorted = useMemo(() => {
    const data = [...filtered];
    data.sort((a, b) => {
      let va = a[sortKey], vb = b[sortKey];
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
    return data;
  }, [filtered, sortKey, sortAsc]);

  const pageCount = Math.ceil(sorted.length / PAGE_SIZE);
  const paged = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const handleSort = (key) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(true); }
  };

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return null;
    return sortAsc ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />;
  };

  return (
    <div>
      {/* Filters */}
      <div className="flex gap-2 mb-4">
        {[
          { key: 'all', label: `All (${nodeResults.length})` },
          { key: 'crime', label: `Crime (${nodeResults.filter((r) => r.is_crime_node).length})` },
          { key: 'clean', label: `Clean (${nodeResults.filter((r) => !r.is_crime_node).length})` },
          { key: 'incorrect', label: `Incorrect (${nodeResults.filter((r) => !r.correct).length})` },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => { setFilterCrime(key); setPage(0); }}
            className={`px-3 py-1.5 rounded-badge text-xs font-medium transition-all ${
              filterCrime === key
                ? 'bg-accent text-white'
                : 'bg-surface-2 text-text-2 hover:text-text-0'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-3 text-text-3">
              {[
                { key: 'node_id', label: 'Node' },
                { key: 'expected_typology', label: 'Expected' },
                { key: 'detected_typology', label: 'Detected' },
                { key: 'correct', label: 'Result' },
                { key: 'confidence', label: 'Conf.' },
                { key: 'entity_f1', label: 'F1' },
                { key: 'assessment_score', label: 'Score' },
                { key: 'duration_ms', label: 'Time' },
              ].map(({ key, label }) => (
                <th
                  key={key}
                  onClick={() => handleSort(key)}
                  className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider cursor-pointer hover:text-text-1 select-none"
                >
                  {label} <SortIcon col={key} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map((r) => (
              <tr
                key={r.node_id}
                className={`border-b border-surface-2 transition-colors ${
                  !r.correct ? 'bg-rose-50/40' : r.is_crime_node ? 'bg-emerald-50/30' : ''
                }`}
              >
                <td className="px-3 py-2 font-mono text-xs text-text-0">{r.node_id}</td>
                <td className="px-3 py-2">
                  <span className={`px-2 py-0.5 rounded-badge text-xs font-medium ${
                    r.expected_typology === 'NONE' ? 'bg-surface-2 text-text-2' :
                    r.expected_typology === 'STRUCTURING' ? 'bg-amber-100 text-amber-700' :
                    r.expected_typology === 'LAYERING' ? 'bg-violet-100 text-violet-700' :
                    'bg-rose-100 text-rose-700'
                  }`}>
                    {r.expected_typology}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <span className={`px-2 py-0.5 rounded-badge text-xs font-medium ${
                    r.detected_typology === 'NONE' ? 'bg-surface-2 text-text-2' :
                    r.detected_typology === 'STRUCTURING' ? 'bg-amber-100 text-amber-700' :
                    r.detected_typology === 'LAYERING' ? 'bg-violet-100 text-violet-700' :
                    'bg-rose-100 text-rose-700'
                  }`}>
                    {r.detected_typology}
                  </span>
                </td>
                <td className="px-3 py-2">
                  {r.correct
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    : <XCircle className="w-4 h-4 text-rose-500" />}
                </td>
                <td className="px-3 py-2 font-mono text-xs">{(r.confidence * 100).toFixed(0)}%</td>
                <td className="px-3 py-2 font-mono text-xs">{(r.entity_f1 * 100).toFixed(0)}%</td>
                <td className="px-3 py-2 font-mono text-xs">{r.assessment_score.toFixed(1)}</td>
                <td className="px-3 py-2 font-mono text-xs text-text-2">{formatMs(r.duration_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pageCount > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-xs text-text-3">
            Showing {page * PAGE_SIZE + 1}-{Math.min((page + 1) * PAGE_SIZE, sorted.length)} of {sorted.length}
          </span>
          <div className="flex gap-1">
            {Array.from({ length: Math.min(pageCount, 10) }, (_, i) => {
              // Show first 3, current-1..current+1, last 3
              const p = i;
              return (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-8 h-8 rounded-btn text-xs font-medium transition-all ${
                    page === p ? 'bg-accent text-white' : 'bg-surface-2 text-text-2 hover:text-text-0'
                  }`}
                >
                  {p + 1}
                </button>
              );
            })}
            {pageCount > 10 && (
              <span className="text-xs text-text-3 self-center px-1">...{pageCount}</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function BenchmarkResults({ benchmark, onReset }) {
  const { aggregate, node_results, config, started_at, completed_at } = benchmark;

  if (!aggregate) return null;

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">
      {/* Section 1: Header Stats */}
      <motion.div variants={fadeUp} className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Crime Detection Rate"
          value={aggregate.crime_detection_rate * 100}
          suffix="%"
          decimals={1}
          icon={Target}
          color="emerald"
        />
        <StatCard
          label="False Positive Rate"
          value={aggregate.false_positive_rate * 100}
          suffix="%"
          decimals={2}
          icon={ShieldAlert}
          color="rose"
        />
        <StatCard
          label="Average F1 Score"
          value={aggregate.avg_f1 * 100}
          suffix="%"
          decimals={1}
          icon={Activity}
          color="accent"
        />
        <StatCard
          label="Total Duration"
          value={aggregate.total_duration_ms / 1000}
          suffix="s"
          decimals={1}
          icon={Clock}
          color="cyan"
        />
      </motion.div>

      {/* Section 2: Detection Gauges */}
      <motion.div variants={fadeUp}>
        <GlowCard className="p-6">
          <h3 className="text-sm font-medium text-text-1 mb-4 uppercase tracking-wider">Detection Breakdown</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="flex flex-col items-center">
              <ScoreGauge score={aggregate.structuring_detection_rate} label="STRUCTURING" />
            </div>
            <div className="flex flex-col items-center">
              <ScoreGauge score={aggregate.layering_detection_rate} label="LAYERING" />
            </div>
            <div className="flex flex-col items-center">
              <ScoreGauge score={aggregate.crime_detection_rate} label="OVERALL" />
            </div>
            <div className="flex flex-col items-center">
              <ScoreGauge score={1 - aggregate.false_positive_rate} label="SPECIFICITY" />
            </div>
          </div>
        </GlowCard>
      </motion.div>

      {/* Section 3: Aggregate Metrics */}
      <motion.div variants={fadeUp}>
        <GlowCard className="p-6">
          <h3 className="text-sm font-medium text-text-1 mb-4 uppercase tracking-wider">Aggregate Entity Metrics</h3>
          <div className="grid grid-cols-3 gap-6">
            <div className="flex flex-col items-center">
              <ScoreGauge score={aggregate.avg_precision} label="PRECISION" />
            </div>
            <div className="flex flex-col items-center">
              <ScoreGauge score={aggregate.avg_recall} label="RECALL" />
            </div>
            <div className="flex flex-col items-center">
              <ScoreGauge score={aggregate.avg_f1} label="F1 SCORE" />
            </div>
          </div>
        </GlowCard>
      </motion.div>

      {/* Section 4: Per-Crime Stats */}
      <motion.div variants={fadeUp}>
        <GlowCard className="p-6">
          <h3 className="text-sm font-medium text-text-1 mb-4 uppercase tracking-wider">Per-Crime Type Statistics</h3>
          <div className="grid grid-cols-2 gap-6">
            <div className="p-4 bg-surface-1 rounded-card border border-surface-2">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-3 h-3 rounded-full bg-amber-500" />
                <span className="text-sm font-medium text-text-0">Structuring</span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-text-2">Crime Nodes</span>
                  <span className="font-mono text-text-0">
                    {node_results.filter((r) => r.expected_typology === 'STRUCTURING' || r.expected_typology === 'BOTH').length}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-2">Correctly Detected</span>
                  <span className="font-mono text-emerald-600">
                    {node_results.filter((r) =>
                      (r.expected_typology === 'STRUCTURING' || r.expected_typology === 'BOTH') &&
                      (r.detected_typology === 'STRUCTURING' || r.detected_typology === 'BOTH')
                    ).length}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-2">Detection Rate</span>
                  <span className="font-mono font-bold text-text-0">
                    {(aggregate.structuring_detection_rate * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>
            <div className="p-4 bg-surface-1 rounded-card border border-surface-2">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-3 h-3 rounded-full bg-violet-500" />
                <span className="text-sm font-medium text-text-0">Layering</span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-text-2">Crime Nodes</span>
                  <span className="font-mono text-text-0">
                    {node_results.filter((r) => r.expected_typology === 'LAYERING' || r.expected_typology === 'BOTH').length}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-2">Correctly Detected</span>
                  <span className="font-mono text-emerald-600">
                    {node_results.filter((r) =>
                      (r.expected_typology === 'LAYERING' || r.expected_typology === 'BOTH') &&
                      (r.detected_typology === 'LAYERING' || r.detected_typology === 'BOTH')
                    ).length}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-2">Detection Rate</span>
                  <span className="font-mono font-bold text-text-0">
                    {(aggregate.layering_detection_rate * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </GlowCard>
      </motion.div>

      {/* Section 5: Score Distribution */}
      <motion.div variants={fadeUp}>
        <GlowCard className="p-6">
          <h3 className="text-sm font-medium text-text-1 mb-4 uppercase tracking-wider">Assessment Score Distribution</h3>
          <ScoreDistributionChart nodeResults={node_results} />
        </GlowCard>
      </motion.div>

      {/* Section 6: Results Table */}
      <motion.div variants={fadeUp}>
        <GlowCard className="p-6">
          <h3 className="text-sm font-medium text-text-1 mb-4 uppercase tracking-wider">Per-Node Investigation Results</h3>
          <ResultsTable nodeResults={node_results} />
        </GlowCard>
      </motion.div>

      {/* Section 7: Config Summary */}
      <motion.div variants={fadeUp}>
        <GlowCard className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex gap-4 text-xs font-mono text-text-3">
              <span>{aggregate.total_investigations} nodes</span>
              <span>difficulty {config.difficulty}</span>
              <span>seed {config.seed}</span>
              <span>{config.hop_depth} hops</span>
              <span>{config.jurisdiction}</span>
              <span>{formatMs(aggregate.total_duration_ms)} total</span>
              <span>{aggregate.avg_duration_ms.toFixed(0)}ms/node avg</span>
            </div>
            <button
              onClick={onReset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-btn bg-surface-2 text-text-2 text-xs font-medium hover:text-text-0 hover:bg-surface-3 transition-all"
            >
              <RotateCcw className="w-3 h-3" />
              New Benchmark
            </button>
          </div>
        </GlowCard>
      </motion.div>
    </motion.div>
  );
}
