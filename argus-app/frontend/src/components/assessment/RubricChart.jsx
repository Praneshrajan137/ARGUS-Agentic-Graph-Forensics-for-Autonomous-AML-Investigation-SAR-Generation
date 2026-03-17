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
  const data = [
    {
      name: 'Pattern',
      weight: 28,
      score: rubric?.pattern?.score || 0,
      fullMark: 100,
    },
    {
      name: 'Evidence',
      weight: 20,
      score: rubric?.evidence?.score || 0,
      fullMark: 100,
    },
    {
      name: 'Narrative',
      weight: 16,
      score: rubric?.narrative?.score || 0,
      fullMark: 100,
    },
    {
      name: 'Completeness',
      weight: 16,
      score: rubric?.completeness?.score || 0,
      fullMark: 100,
    },
    {
      name: 'Efficiency',
      weight: 20,
      score: rubric?.efficiency?.score || 0,
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
              fontFamily: 'JetBrains Mono',
            }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={90}
            tick={{
              fontSize: 13,
              fill: 'var(--text-1)',
              fontFamily: 'DM Sans',
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
                fontFamily: 'JetBrains Mono',
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
