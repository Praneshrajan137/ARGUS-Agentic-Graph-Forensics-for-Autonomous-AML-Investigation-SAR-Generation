import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
  LabelList,
} from 'recharts';

const RUBRIC_COLORS = {
  Pattern: 'var(--amber-base)',
  Evidence: 'var(--cyan-base)',
  Narrative: 'var(--violet-base)',
  Completeness: 'var(--emerald-base)',
  Efficiency: 'var(--accent-base)',
};

/**
 * Horizontal bar chart showing 5 rubric categories with their scores.
 *
 * @param {{ rubric: Record<string, { weight: number, score: number }> | null }} props
 */
export default function RubricChart({ rubric }) {
  // rubric can be either { pattern_detection: 0.8, ... } (flat floats)
  // or { pattern: { score: 80 }, ... } (nested objects) — handle both
  const getScore = (key, altKey) => {
    if (!rubric) return 0;
    // Flat float (0.0–1.0) from backend
    if (typeof rubric[key] === 'number') return Math.round(rubric[key] * 100);
    // Nested object form
    if (typeof rubric[altKey]?.score === 'number') return Math.round(rubric[altKey].score);
    if (typeof rubric[altKey] === 'number') return Math.round(rubric[altKey] * 100);
    return 0;
  };

  const data = [
    {
      name: 'Pattern',
      weight: 28,
      score: getScore('pattern_detection', 'pattern'),
      fullMark: 100,
    },
    {
      name: 'Evidence',
      weight: 20,
      score: getScore('evidence_analysis', 'evidence'),
      fullMark: 100,
    },
    {
      name: 'Narrative',
      weight: 16,
      score: getScore('narrative_quality', 'narrative'),
      fullMark: 100,
    },
    {
      name: 'Completeness',
      weight: 16,
      score: getScore('completeness', 'completeness'),
      fullMark: 100,
    },
    {
      name: 'Efficiency',
      weight: 20,
      score: getScore('efficiency', 'efficiency'),
      fullMark: 100,
    },
  ];

  return (
    <div className="w-full" style={{ height: 280 }} data-testid="rubric-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 0, right: 40, bottom: 0, left: 100 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--surface-3)"
            horizontal={false}
          />
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{
              fontSize: 11,
              fill: 'var(--text-3)',
              fontFamily: 'var(--font-mono)',
            }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={90}
            tick={{
              fontSize: 13,
              fill: 'var(--text-1)',
              fontFamily: 'var(--font-body)',
              fontWeight: 500,
            }}
          />
          {/* Background bar (weight indicator) */}
          <Bar
            dataKey="fullMark"
            fill="var(--surface-2)"
            radius={[0, 4, 4, 0]}
            barSize={24}
          />
          {/* Score bar */}
          <Bar
            dataKey="score"
            radius={[0, 4, 4, 0]}
            barSize={24}
            animationDuration={800}
            animationEasing="ease-out"
          >
            {data.map((entry) => (
              <Cell
                key={entry.name}
                fill={RUBRIC_COLORS[entry.name] || 'var(--accent-base)'}
              />
            ))}
            <LabelList
              dataKey="score"
              position="right"
              formatter={(v) => `${v}%`}
              style={{
                fontSize: 12,
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                fill: 'var(--text-1)',
              }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
