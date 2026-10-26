// Renders a ```chart block from an answer. Loaded lazily (Recharts is big), so
// it costs nothing until an answer actually contains a chart.
//
// Spec (JSON):
//   { "type": "bar" | "line" | "area" | "pie" | "donut" | "radial",
//     "title": "Attendance by course", "unit": "%", "target": 75,
//     "data": [ { "label": "CSE329", "value": 90.9 }, ... ] }
// More than one numeric key per item ({"label", "Attended", "Delivered"})
// draws one series per key.
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  PolarAngleAxis, RadialBar, RadialBarChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

export type ChartSpec = {
  type?: string
  title?: string
  unit?: string
  target?: number
  data: Record<string, string | number>[]
}

const PALETTE = ['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6', '#f43f5e', '#06b6d4', '#84cc16', '#ec4899']
const GOOD = '#10b981'
const LOW = '#f43f5e'

function seriesOf(data: ChartSpec['data']): string[] {
  const keys = new Set<string>()
  for (const row of data) for (const [k, v] of Object.entries(row)) if (k !== 'label' && typeof v === 'number') keys.add(k)
  return [...keys]
}

export default function ChartBlock({ spec }: { spec: ChartSpec }) {
  const data: Record<string, string | number>[] = spec.data.map(row => ({ ...row, label: String(row.label ?? '') }))
  const series = seriesOf(data)
  const unit = spec.unit ?? ''
  const type = (spec.type ?? 'bar').toLowerCase()
  // Currency goes in front with Indian digit grouping (₹1,46,700); other units after (90.9%).
  const currency = /^[₹$€£¥]$|^(rs\.?|inr)$/i.test(unit.trim())
  const fmt = (v: unknown) => {
    if (typeof v !== 'number') return String(v)
    const number = v.toLocaleString('en-IN', { maximumFractionDigits: 1 })
    return currency ? `${unit.trim() === '₹' || /rs|inr/i.test(unit) ? '₹' : unit.trim()}${number}` : `${number}${unit}`
  }
  // Axis ticks use compact numbers (₹1.5L, 12K) and an axis wide enough for them.
  const compact = (v: unknown) => {
    if (typeof v !== 'number') return String(v)
    const short = Math.abs(v) >= 1000 ? new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 }).format(v) : String(Math.round(v * 10) / 10)
    return currency ? `${unit.trim() === '₹' || /rs|inr/i.test(unit) ? '₹' : unit.trim()}${short}` : `${short}${unit}`
  }
  const values = data.flatMap(row => series.map(k => Number(row[k]) || 0))
  const yWidth = Math.max(36, Math.max(...values.map(v => compact(v).length), 3) * 7.5 + 10)
  const axis = { stroke: 'var(--muted)', fontSize: 12, tickLine: false, axisLine: false } as const
  const tooltip = (
    <Tooltip
      formatter={(v: unknown, name: unknown) => [fmt(v), String(name) === 'value' ? spec.title ?? 'Value' : String(name)]}
      contentStyle={{ background: 'var(--sidebar)', border: '1px solid var(--line)', borderRadius: 10, color: 'var(--ink)', fontSize: 13 }}
      itemStyle={{ color: 'var(--ink)' }}
      labelStyle={{ color: 'var(--muted)' }}
      cursor={{ fill: 'var(--hover)' }}
    />
  )
  const target = typeof spec.target === 'number'
    ? <ReferenceLine y={spec.target} stroke={LOW} strokeDasharray="5 4" label={{ value: `Target ${fmt(spec.target)}`, fill: LOW, fontSize: 11, position: 'insideTopRight' }} />
    : null
  const single = series.length === 1

  let chart
  if (type === 'pie' || type === 'donut') {
    const key = series[0] ?? 'value'
    chart = (
      <PieChart>
        {tooltip}
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Pie data={data} dataKey={key} nameKey="label" innerRadius={type === 'donut' ? '55%' : 0} outerRadius="85%" paddingAngle={type === 'donut' ? 2 : 0} stroke="var(--bg)">
          {data.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
        </Pie>
      </PieChart>
    )
  } else if (type === 'radial') {
    // Progress rings: best for percentages of a whole, e.g. attendance per course.
    const key = series[0] ?? 'value'
    const max = spec.unit === '%' ? 100 : Math.max(...data.map(d => Number(d[key]) || 0), 1)
    const rows = data.map((d, i) => ({
      ...d,
      fill: typeof spec.target === 'number' ? (Number(d[key]) >= spec.target ? GOOD : LOW) : PALETTE[i % PALETTE.length],
    }))
    chart = (
      <RadialBarChart data={rows} innerRadius="22%" outerRadius="100%" startAngle={90} endAngle={-270} barSize={10}>
        <PolarAngleAxis type="number" domain={[0, max]} tick={false} />
        <RadialBar dataKey={key} background={{ fill: 'var(--hover)' }} cornerRadius={6} />
        {tooltip}
        <Legend iconSize={10} layout="vertical" verticalAlign="middle" align="right" wrapperStyle={{ fontSize: 12 }}
          formatter={(_v: unknown, entry: unknown) => {
            const row = (entry as { payload?: Record<string, unknown> }).payload ?? {}
            return `${row.label} · ${fmt(row[key])}`
          }} />
      </RadialBarChart>
    )
  } else if (type === 'line' || type === 'area') {
    const Chart = type === 'line' ? LineChart : AreaChart
    chart = (
      <Chart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <defs>
          {series.map((s, i) => (
            <linearGradient key={s} id={`grad-${i}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={PALETTE[i % PALETTE.length]} stopOpacity={0.35} />
              <stop offset="100%" stopColor={PALETTE[i % PALETTE.length]} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid stroke="var(--line)" vertical={false} />
        <XAxis dataKey="label" {...axis} />
        <YAxis {...axis} tickFormatter={compact} width={yWidth} />
        {tooltip}
        {!single && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {target}
        {series.map((s, i) => type === 'line'
          ? <Line key={s} type="monotone" dataKey={s} stroke={PALETTE[i % PALETTE.length]} strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
          : <Area key={s} type="monotone" dataKey={s} stroke={PALETTE[i % PALETTE.length]} strokeWidth={2.5} fill={`url(#grad-${i})`} />)}
      </Chart>
    )
  } else {
    chart = (
      <BarChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--line)" vertical={false} />
        <XAxis dataKey="label" {...axis} interval={0} />
        <YAxis {...axis} tickFormatter={compact} width={yWidth} />
        {tooltip}
        {!single && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {target}
        {series.map((s, i) => (
          <Bar key={s} dataKey={s} radius={[6, 6, 0, 0]} maxBarSize={44} fill={PALETTE[i % PALETTE.length]}>
            {/* One series against a target: green when it meets it, red when not. */}
            {single && typeof spec.target === 'number' &&
              data.map((row, j) => <Cell key={j} fill={Number(row[s]) >= spec.target! ? GOOD : LOW} />)}
          </Bar>
        ))}
      </BarChart>
    )
  }

  return (
    <figure className="chart-card">
      {spec.title && <figcaption>{spec.title}</figcaption>}
      <div className="chart-body">
        <ResponsiveContainer width="100%" height="100%">{chart}</ResponsiveContainer>
      </div>
    </figure>
  )
}
