<template>
  <div class="solution-summary">
    <div v-for="item in items" :key="item.label" class="metric-card">
      <span class="metric-label">{{ item.label }}</span>
      <span class="metric-value" :class="item.valueClass">{{ item.value }}</span>
      <span v-if="item.sub" class="metric-sub">{{ item.sub }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatNumber } from '@/api/dataService'

const props = defineProps({
  metrics: { type: Object, required: true },
  variant: { type: String, default: 'initial' }, // initial | optimized
})

const items = computed(() => [
  {
    label: '平均满足率',
    value: `${props.metrics.satisfaction_rate.toFixed(2)}%`,
    valueClass: props.variant === 'optimized' ? 'accent' : '',
  },
  {
    label: '公平性指数',
    value: props.metrics.fairness.toFixed(4),
  },
  {
    label: '紧急程度得分',
    value: props.metrics.urgency_score.toFixed(4),
  },
  {
    label: '时间效率',
    value: props.metrics.time_efficiency.toFixed(4),
  },
  {
    label: '运输成本',
    value: formatNumber(props.metrics.transport_cost),
    sub: props.variant === 'optimized' ? '优化后' : '初始方案',
  },
])
</script>

<style scoped>
.solution-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.metric-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.metric-value {
  font-size: 18px;
  font-weight: 700;
}

.metric-value.accent {
  color: var(--improvement);
}

.metric-sub {
  font-size: 11px;
  color: var(--text-secondary);
}
</style>
