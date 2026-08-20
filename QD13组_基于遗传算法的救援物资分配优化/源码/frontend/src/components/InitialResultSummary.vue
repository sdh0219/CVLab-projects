<template>
  <div class="initial-result">
    <div class="metric-row">
      <div v-for="item in items" :key="item.label" class="metric-item">
        <span class="label">{{ item.label }}</span>
        <span class="value">{{ item.value }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatNumber } from '@/api/dataService'

const props = defineProps({
  metrics: { type: Object, required: true },
})

const items = computed(() => [
  { label: '满足率', value: `${props.metrics.satisfaction_rate.toFixed(2)}%` },
  { label: '公平性', value: props.metrics.fairness.toFixed(4) },
  { label: '紧急程度', value: props.metrics.urgency_score.toFixed(4) },
  { label: '时间效率', value: props.metrics.time_efficiency.toFixed(4) },
  { label: '运输成本', value: formatNumber(props.metrics.transport_cost) },
])
</script>

<style scoped>
.initial-result {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 18px;
  margin-bottom: 16px;
}

.metric-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
}

.metric-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
}

.metric-item .label {
  color: var(--text-secondary);
}

.metric-item .value {
  font-weight: 600;
  color: var(--text-primary);
}
</style>
