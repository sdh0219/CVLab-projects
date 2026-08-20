<template>
  <div class="chart-card">
    <div class="chart-header">
      <h3>各受灾点物资满足率对比</h3>
      <p>优化前后各受灾点的综合物资满足率</p>
    </div>
    <v-chart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps({
  pointNames: { type: Array, required: true },
  initialSatisfaction: { type: Array, required: true },
  optimizedSatisfaction: { type: Array, required: true }
})

const chartOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#1e2a3a',
    borderColor: '#2d3f54',
    textStyle: { color: '#e8edf4' },
    formatter: (params) => {
      let html = `<strong>${params[0].axisValue}</strong><br/>`
      params.forEach((p) => {
        html += `${p.marker} ${p.seriesName}: ${p.value.toFixed(2)}%<br/>`
      })
      return html
    }
  },
  legend: {
    data: ['优化前', '优化后'],
    textStyle: { color: '#8b9cb3' },
    top: 0
  },
  grid: { left: '3%', right: '4%', bottom: '12%', top: '15%', containLabel: true },
  xAxis: {
    type: 'category',
    data: props.pointNames,
    axisLine: { lineStyle: { color: '#2d3f54' } },
    axisLabel: { color: '#8b9cb3', rotate: 30 }
  },
  yAxis: {
    type: 'value',
    name: '满足率 (%)',
    nameTextStyle: { color: '#8b9cb3' },
    axisLine: { show: false },
    splitLine: { lineStyle: { color: '#2d3f54', type: 'dashed' } },
    axisLabel: { color: '#8b9cb3' }
  },
  series: [
    {
      name: '优化前',
      type: 'bar',
      data: props.initialSatisfaction,
      itemStyle: { color: '#64748b', borderRadius: [4, 4, 0, 0] },
      barMaxWidth: 36
    },
    {
      name: '优化后',
      type: 'bar',
      data: props.optimizedSatisfaction,
      itemStyle: { color: '#4ade80', borderRadius: [4, 4, 0, 0] },
      barMaxWidth: 36
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
  margin-bottom: 12px;
}

.chart {
  height: 360px;
  width: 100%;
}
</style>
