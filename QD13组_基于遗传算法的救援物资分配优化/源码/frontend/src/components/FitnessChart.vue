<template>
  <div class="chart-card">
    <div class="chart-header">
      <h3>{{ title }}</h3>
      <p>{{ subtitle }}</p>
      <div v-if="fitnessHistory.length" class="fitness-stats">
        <span>初始适应度 <strong>{{ initialFitness.toFixed(4) }}</strong></span>
        <span>最终适应度 <strong class="final">{{ finalFitness.toFixed(4) }}</strong></span>
        <span v-if="improvement > 0" class="improve">
          提升 {{ (improvement * 100).toFixed(2) }}%
        </span>
      </div>
    </div>
    <v-chart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const props = defineProps({
  fitnessHistory: { type: Array, required: true },
  title: { type: String, default: '遗传算法迭代过程' },
  subtitle: { type: String, default: '每代全局最优适应度变化曲线（单调不降）' },
  initialFitness: { type: Number, default: null },
  finalFitness: { type: Number, default: null },
})

const initialFitness = computed(() =>
  props.initialFitness ?? props.fitnessHistory[0] ?? 0
)
const finalFitness = computed(() =>
  props.finalFitness ?? props.fitnessHistory[props.fitnessHistory.length - 1] ?? 0
)
const improvement = computed(() => {
  if (!initialFitness.value) return 0
  return (finalFitness.value - initialFitness.value) / initialFitness.value
})

const chartOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#1e2a3a',
    borderColor: '#2d3f54',
    textStyle: { color: '#e8edf4' },
    formatter: (params) => {
      const p = params[0]
      return `第 ${p.axisValue} 代<br/>平均适应度: <strong>${p.value.toFixed(4)}</strong>`
    }
  },
  grid: { left: '3%', right: '4%', bottom: '8%', top: '10%', containLabel: true },
  xAxis: {
    type: 'category',
    name: '迭代代数',
    nameTextStyle: { color: '#8b9cb3' },
    data: props.fitnessHistory.map((_, i) => i + 1),
    axisLine: { lineStyle: { color: '#2d3f54' } },
    axisLabel: { color: '#8b9cb3' }
  },
  yAxis: {
    type: 'value',
    name: '适应度',
    nameTextStyle: { color: '#8b9cb3' },
    axisLine: { show: false },
    splitLine: { lineStyle: { color: '#2d3f54', type: 'dashed' } },
    axisLabel: { color: '#8b9cb3' }
  },
  series: [
    {
      type: 'line',
      data: props.fitnessHistory,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: '#22c55e', width: 2 },
      itemStyle: { color: '#22c55e' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(34, 197, 94, 0.35)' },
            { offset: 1, color: 'rgba(34, 197, 94, 0.02)' }
          ]
        }
      }
    }
  ]
}))
</script>

<style scoped>
.chart-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  height: 100%;
}

.chart-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}

.chart-header p {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.fitness-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.fitness-stats strong {
  color: var(--text-primary);
}

.fitness-stats .final {
  color: var(--improvement);
}

.fitness-stats .improve {
  color: var(--improvement);
  font-weight: 600;
}

.chart {
  height: 360px;
  width: 100%;
}
</style>
