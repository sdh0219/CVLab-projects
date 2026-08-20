<template>
  <div class="summary-grid">
    <div v-for="item in items" :key="item.label" class="summary-card">
      <div class="card-icon" :style="{ background: item.color }">{{ item.icon }}</div>
      <div class="card-body">
        <span class="card-label">{{ item.label }}</span>
        <span class="card-value">{{ item.value }}</span>
        <span v-if="item.sub" class="card-sub" :class="item.subClass">{{ item.sub }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatNumber } from '@/api/dataService'

const props = defineProps({
  summary: { type: Object, required: true },
  initialMetrics: { type: Object, required: true },
  optimizedMetrics: { type: Object, required: true }
})

const satisfactionDelta = computed(() =>
  props.optimizedMetrics.satisfaction_rate - props.initialMetrics.satisfaction_rate
)

const items = computed(() => [
  {
    icon: '📍',
    label: '受灾点',
    value: props.summary.disasterPointsCount,
    sub: '个区域',
    color: 'rgba(59, 130, 246, 0.2)'
  },
  {
    icon: '🏭',
    label: '储备仓库',
    value: props.summary.warehousesCount,
    sub: '个仓库',
    color: 'rgba(34, 197, 94, 0.2)'
  },
  {
    icon: '📦',
    label: '物资类型',
    value: props.summary.materialsCount,
    sub: props.summary.materialNames?.join('、') || '',
    color: 'rgba(245, 158, 11, 0.2)'
  },
  {
    icon: '👥',
    label: '受灾人口',
    value: formatNumber(props.summary.totalPopulation),
    sub: '总计',
    color: 'rgba(239, 68, 68, 0.2)'
  },
  {
    icon: '✅',
    label: '优化后满足率',
    value: `${props.optimizedMetrics.satisfaction_rate.toFixed(2)}%`,
    sub:
      satisfactionDelta.value >= 0
        ? `提升 ${satisfactionDelta.value.toFixed(2)}%`
        : `下降 ${Math.abs(satisfactionDelta.value).toFixed(2)}%`,
    subClass:
      satisfactionDelta.value > 0
        ? 'improvement'
        : satisfactionDelta.value < 0
          ? 'decline'
          : '',
    color: 'rgba(34, 197, 94, 0.2)'
  },
  {
    icon: '🚚',
    label: '运输成本',
    value: formatNumber(props.optimizedMetrics.transport_cost),
    sub: '优化后方案',
    color: 'rgba(139, 156, 179, 0.2)'
  }
])
</script>

<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.summary-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: border-color 0.2s, transform 0.2s;
}

.summary-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
}

.card-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  font-size: 20px;
  flex-shrink: 0;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.card-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.card-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.card-sub {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-sub.improvement {
  color: var(--improvement);
  font-weight: 600;
}

.card-sub.decline {
  color: var(--danger);
  font-weight: 600;
}
</style>
