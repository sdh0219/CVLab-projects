<template>
  <div class="opt-result">
    <div class="hero-row">
      <div class="hero-card primary">
        <span class="hero-label">物资满足率</span>
        <div class="hero-compare">
          <span class="val-before">{{ fmtPct(initialMetrics.satisfaction_rate) }}</span>
          <span class="arrow">→</span>
          <span class="val-after">{{ fmtPct(optimizedMetrics.satisfaction_rate) }}</span>
        </div>
        <span class="hero-delta" :class="deltaClass(satisfactionDelta)">
          {{ fmtDelta(satisfactionDelta, '%') }}
        </span>
      </div>

      <div class="hero-card">
        <span class="hero-label">综合适应度</span>
        <div class="hero-compare">
          <span class="val-before">{{ fmtNum(initialFitness, 4) }}</span>
          <span class="arrow">→</span>
          <span class="val-after">{{ fmtNum(finalFitness, 4) }}</span>
        </div>
        <span class="hero-delta" :class="deltaClass(fitnessDelta)">
          {{ fmtDelta(fitnessDelta * 100, '%') }}
        </span>
      </div>

      <div class="hero-card">
        <span class="hero-label">调运路线</span>
        <span class="hero-single">{{ transportPlan?.routeCount ?? 0 }} 条</span>
        <span class="hero-sub">总调运 {{ formatNumber(transportPlan?.totalShipped ?? 0) }}</span>
      </div>

      <div class="hero-card">
        <span class="hero-label">资源缺口</span>
        <span class="hero-single" :class="gapClass">{{ gapRate }}</span>
        <span class="hero-sub">
          需求 {{ formatNumber(summary.totalDemand) }} / 库存 {{ formatNumber(summary.totalInventory) }}
        </span>
      </div>
    </div>

    <div class="metrics-table-wrap">
      <h4>多目标指标对比</h4>
      <table class="metrics-table">
        <thead>
          <tr>
            <th>评价指标</th>
            <th>权重</th>
            <th>初始方案</th>
            <th>优化后</th>
            <th>变化</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in metricRows" :key="row.key">
            <td class="metric-name">{{ row.name }}</td>
            <td class="metric-weight">{{ row.weight }}</td>
            <td>{{ row.initial }}</td>
            <td class="val-highlight">{{ row.optimized }}</td>
            <td :class="deltaClass(row.delta)">{{ row.deltaText }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatNumber } from '@/api/dataService'

const props = defineProps({
  summary: { type: Object, required: true },
  initialMetrics: { type: Object, required: true },
  optimizedMetrics: { type: Object, required: true },
  initialFitness: { type: Number, default: 0 },
  finalFitness: { type: Number, default: 0 },
  transportPlan: { type: Object, default: null },
})

const WEIGHTS = {
  satisfaction: '35%',
  cost: '15%',
  fairness: '20%',
  urgency: '20%',
  time: '10%',
}

const satisfactionDelta = computed(() =>
  props.optimizedMetrics.satisfaction_rate - props.initialMetrics.satisfaction_rate
)

const fitnessDelta = computed(() => {
  if (!props.initialFitness) return 0
  return (props.finalFitness - props.initialFitness) / props.initialFitness
})

const gapRate = computed(() => {
  const demand = props.summary.totalDemand || 0
  const inventory = props.summary.totalInventory || 0
  if (demand <= 0) return '-'
  const gap = ((demand - inventory) / demand) * 100
  return gap > 0 ? `缺口 ${gap.toFixed(1)}%` : '库存充足'
})

const gapClass = computed(() => {
  const demand = props.summary.totalDemand || 0
  const inventory = props.summary.totalInventory || 0
  return demand > inventory ? 'warn' : 'ok'
})

const metricRows = computed(() => {
  const rows = [
    {
      key: 'satisfaction',
      name: '物资满足率',
      weight: WEIGHTS.satisfaction,
      initial: fmtPct(props.initialMetrics.satisfaction_rate),
      optimized: fmtPct(props.optimizedMetrics.satisfaction_rate),
      delta: props.optimizedMetrics.satisfaction_rate - props.initialMetrics.satisfaction_rate,
      isPct: true,
    },
    {
      key: 'fairness',
      name: '公平性指数',
      weight: WEIGHTS.fairness,
      initial: props.initialMetrics.fairness.toFixed(4),
      optimized: props.optimizedMetrics.fairness.toFixed(4),
      delta: props.optimizedMetrics.fairness - props.initialMetrics.fairness,
      isPct: false,
    },
    {
      key: 'urgency',
      name: '紧急程度得分',
      weight: WEIGHTS.urgency,
      initial: props.initialMetrics.urgency_score.toFixed(4),
      optimized: props.optimizedMetrics.urgency_score.toFixed(4),
      delta: calcRelDelta(props.initialMetrics.urgency_score, props.optimizedMetrics.urgency_score),
      isPct: false,
      rel: true,
    },
    {
      key: 'time',
      name: '时间效率',
      weight: WEIGHTS.time,
      initial: props.initialMetrics.time_efficiency.toFixed(4),
      optimized: props.optimizedMetrics.time_efficiency.toFixed(4),
      delta: calcRelDelta(props.initialMetrics.time_efficiency, props.optimizedMetrics.time_efficiency),
      isPct: false,
      rel: true,
    },
    {
      key: 'cost',
      name: '运输成本',
      weight: WEIGHTS.cost,
      initial: formatNumber(props.initialMetrics.transport_cost),
      optimized: formatNumber(props.optimizedMetrics.transport_cost),
      delta: calcRelDelta(props.initialMetrics.transport_cost, props.optimizedMetrics.transport_cost),
      isPct: false,
      rel: true,
      invert: true,
    },
  ]

  return rows.map((r) => ({
    ...r,
    deltaText: r.isPct
      ? fmtDelta(r.delta, '%')
      : fmtRelDeltaText(r.delta, r.invert),
  }))
})

function fmtPct(v) {
  return `${Number(v).toFixed(2)}%`
}

function fmtNum(v, d = 2) {
  return Number(v).toFixed(d)
}

function fmtDelta(v, unit = '') {
  const sign = v >= 0 ? '+' : ''
  return `${sign}${Number(v).toFixed(2)}${unit}`
}

function calcRelDelta(before, after) {
  if (Math.abs(before) < 1e-10) return after > 0 ? 1 : 0
  return (after - before) / Math.abs(before)
}

function fmtRelDeltaText(ratio, invert = false) {
  const pct = ratio * 100
  const effective = invert ? -pct : pct
  const sign = effective >= 0 ? '+' : ''
  return `${sign}${effective.toFixed(1)}%`
}

function deltaClass(delta) {
  if (typeof delta === 'number' && Math.abs(delta) < 1e-6) return ''
  return delta > 0 ? 'positive' : 'negative'
}
</script>

<style scoped>
.opt-result {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 20px;
}

.hero-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}

.hero-card {
  padding: 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 10px;
}

.hero-card.primary {
  border-color: rgba(74, 222, 128, 0.35);
  background: rgba(34, 197, 94, 0.06);
}

.hero-label {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.hero-compare {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.val-before {
  font-size: 16px;
  color: var(--text-secondary);
}

.arrow {
  color: var(--text-secondary);
  font-size: 14px;
}

.val-after {
  font-size: 22px;
  font-weight: 700;
  color: var(--improvement);
}

.hero-single {
  display: block;
  font-size: 22px;
  font-weight: 700;
}

.hero-single.warn {
  color: var(--warning);
}

.hero-single.ok {
  color: var(--improvement);
}

.hero-delta {
  display: inline-block;
  margin-top: 6px;
  font-size: 13px;
  font-weight: 600;
}

.hero-delta.positive {
  color: var(--improvement);
}

.hero-delta.negative {
  color: var(--danger);
}

.hero-sub {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-secondary);
}

.metrics-table-wrap h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.metrics-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.metrics-table th,
.metrics-table td {
  padding: 10px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

.metrics-table th {
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 12px;
}

.metric-name {
  font-weight: 500;
}

.metric-weight {
  color: var(--text-secondary);
  font-size: 12px;
}

.val-highlight {
  color: var(--accent-light);
  font-weight: 600;
}

.positive {
  color: var(--improvement);
  font-weight: 600;
}

.negative {
  color: var(--danger);
  font-weight: 600;
}
</style>
