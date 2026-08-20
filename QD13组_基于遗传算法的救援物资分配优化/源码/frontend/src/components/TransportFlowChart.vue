<template>
  <div class="flow-chart">
    <div class="chart-header">
      <h4>{{ title }}</h4>
      <p>{{ subtitle }}</p>
    </div>
    <v-chart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { SankeyChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, SankeyChart, TooltipComponent])

const props = defineProps({
  routes: { type: Array, required: true },
  title: { type: String, default: '物资调运流向图' },
  subtitle: { type: String, default: '仓库 → 受灾点 物资调运总量（全部物资合计）' },
  maxRoutes: { type: Number, default: 20 },
})

const chartOption = computed(() => {
  const topRoutes = props.routes.slice(0, props.maxRoutes)
  const nodes = []
  const nodeSet = new Set()
  const links = []

  topRoutes.forEach((r) => {
    const from = `仓库·${r.warehouseName}`
    const to = `受灾点·${r.pointName}`
    if (!nodeSet.has(from)) {
      nodeSet.add(from)
      nodes.push({ name: from })
    }
    if (!nodeSet.has(to)) {
      nodeSet.add(to)
      nodes.push({ name: to })
    }
    links.push({ source: from, target: to, value: r.totalAmount })
  })

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#1e2a3a',
      borderColor: '#2d3f54',
      textStyle: { color: '#e8edf4' },
      formatter: (p) => {
        if (p.dataType === 'edge') {
          return `${p.data.source} → ${p.data.target}<br/>调运量: <strong>${p.data.value.toLocaleString()}</strong>`
        }
        return p.name
      },
    },
    series: [
      {
        type: 'sankey',
        layout: 'none',
        emphasis: { focus: 'adjacency' },
        nodeAlign: 'justify',
        lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.45 },
        label: { color: '#8b9cb3', fontSize: 11 },
        data: nodes,
        links,
        left: '4%',
        right: '8%',
        top: '4%',
        bottom: '4%',
      },
    ],
  }
})
</script>

<style scoped>
.flow-chart {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-top: 16px;
}

.chart-header h4 {
  font-size: 15px;
  margin-bottom: 4px;
}

.chart-header p {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.chart {
  height: 360px;
  width: 100%;
}
</style>
