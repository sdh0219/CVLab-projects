<template>
  <div class="chart-card">
    <div class="chart-header">
      <h3>{{ title }}</h3>
      <p>{{ subtitle }}</p>
    </div>
    <v-chart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent])

const props = defineProps({
  warehouseNames: { type: Array, required: true },
  pointNames: { type: Array, required: true },
  allocationMatrix: { type: Array, required: true },
  title: { type: String, default: '物资分配热力图' },
  subtitle: { type: String, default: '各仓库向受灾点的物资分配总量（全部物资合计）' },
})

const chartOption = computed(() => {
  const data = []
  let maxVal = 0
  props.allocationMatrix.forEach((row, wi) => {
    row.forEach((val, pi) => {
      data.push([pi, wi, val])
      if (val > maxVal) maxVal = val
    })
  })

  const showLabels = props.pointNames.length <= 20

  return {
    backgroundColor: 'transparent',
    tooltip: {
      position: 'top',
      backgroundColor: '#1e2a3a',
      borderColor: '#2d3f54',
      textStyle: { color: '#e8edf4' },
      formatter: (p) => {
        const [pi, wi, val] = p.data
        return `${props.warehouseNames[wi]} → ${props.pointNames[pi]}<br/>分配量: <strong>${Math.round(val).toLocaleString()}</strong>`
      }
    },
    grid: {
      left: '12%',
      right: '12%',
      bottom: props.pointNames.length > 20 ? '22%' : '15%',
      top: '5%'
    },
    xAxis: {
      type: 'category',
      data: props.pointNames,
      axisLine: { lineStyle: { color: '#2d3f54' } },
      axisLabel: {
        color: '#8b9cb3',
        rotate: props.pointNames.length > 20 ? 60 : 30,
        fontSize: props.pointNames.length > 20 ? 9 : 11,
        interval: props.pointNames.length > 30 ? 2 : 0
      },
      splitArea: { show: true, areaStyle: { color: ['rgba(30,42,58,0.3)', 'rgba(30,42,58,0.6)'] } }
    },
    yAxis: {
      type: 'category',
      data: props.warehouseNames,
      axisLine: { lineStyle: { color: '#2d3f54' } },
      axisLabel: { color: '#8b9cb3' },
      splitArea: { show: true, areaStyle: { color: ['rgba(30,42,58,0.3)', 'rgba(30,42,58,0.6)'] } }
    },
    visualMap: {
      min: 0,
      max: maxVal || 1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: {
        color: ['#1e3a5f', '#3b82f6', '#f59e0b', '#ef4444']
      },
      textStyle: { color: '#8b9cb3' }
    },
    series: [
      {
        type: 'heatmap',
        data,
        label: {
          show: showLabels,
          formatter: (p) => p.data[2] > 0 ? Math.round(p.data[2]).toLocaleString() : '',
          color: '#e8edf4',
          fontSize: 11
        },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' }
        }
      }
    ]
  }
})
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
  height: 380px;
  width: 100%;
}
</style>
