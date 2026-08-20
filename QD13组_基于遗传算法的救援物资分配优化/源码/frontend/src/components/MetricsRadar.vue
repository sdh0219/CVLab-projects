<template>
  <div class="chart-card">
    <div class="chart-header">
      <h3>综合指标对比</h3>
      <p>优化前后各评价指标得分与提升幅度（按适应度函数统一换算）</p>
    </div>

    <!-- 主图：分组柱状图，各指标独立展示实际得分 -->
    <v-chart class="chart chart-bar" :option="barOption" autoresize />

    <!-- 副图：提升幅度横向条，直观对比优化效果 -->
    <div class="improvement-section">
      <h4>优化提升幅度</h4>
      <v-chart class="chart chart-improve" :option="improveOption" autoresize />
    </div>
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
  initialMetrics: { type: Object, required: true },
  optimizedMetrics: { type: Object, required: true },
})

/** 与后端 fitness() 一致的子目标得分（0~1 量级） */
const METRICS = [
  { key: 'satisfaction', name: '满足率', weight: 0.35 },
  { key: 'cost', name: '成本效益', weight: 0.15 },
  { key: 'fairness', name: '公平性', weight: 0.2 },
  { key: 'urgency', name: '紧急程度', weight: 0.2 },
  { key: 'time', name: '时间效率', weight: 0.1 },
]

function componentScores(metrics) {
  return {
    satisfaction: metrics.satisfaction_rate / 100,
    cost: 1 / (1 + metrics.transport_cost / 10000),
    fairness: metrics.fairness,
    urgency: metrics.urgency_score,
    time: metrics.time_efficiency,
  }
}

function fmtScore(key, val) {
  if (key === 'satisfaction') return `${(val * 100).toFixed(2)}%`
  if (key === 'cost') return val.toFixed(4)
  return val.toFixed(4)
}

function calcImprovement(initial, optimized) {
  if (Math.abs(initial) < 1e-10) {
    return optimized > 0 ? 100 : 0
  }
  return ((optimized - initial) / Math.abs(initial)) * 100
}

const initialScores = computed(() => componentScores(props.initialMetrics))
const optimizedScores = computed(() => componentScores(props.optimizedMetrics))

const barOption = computed(() => {
  const names = METRICS.map((m) => m.name)
  const initialData = METRICS.map((m) => +initialScores.value[m.key].toFixed(4))
  const optimizedData = METRICS.map((m) => +optimizedScores.value[m.key].toFixed(4))

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1e2a3a',
      borderColor: '#2d3f54',
      textStyle: { color: '#e8edf4' },
      formatter: (params) => {
        const idx = params[0].dataIndex
        const m = METRICS[idx]
        const init = initialScores.value[m.key]
        const opt = optimizedScores.value[m.key]
        const delta = calcImprovement(init, opt)
        return `<strong>${m.name}</strong>（权重 ${(m.weight * 100).toFixed(0)}%）<br/>`
          + `优化前: ${fmtScore(m.key, init)}<br/>`
          + `优化后: ${fmtScore(m.key, opt)}<br/>`
          + `变化: <strong>${delta >= 0 ? '+' : ''}${delta.toFixed(1)}%</strong>`
      },
    },
    legend: {
      data: ['优化前', '优化后'],
      textStyle: { color: '#8b9cb3' },
      top: 0,
    },
    grid: { left: '3%', right: '4%', bottom: '8%', top: '14%', containLabel: true },
    xAxis: {
      type: 'category',
      data: names,
      axisLine: { lineStyle: { color: '#2d3f54' } },
      axisLabel: { color: '#8b9cb3', fontSize: 12 },
    },
    yAxis: {
      type: 'value',
      name: '适应度子得分',
      nameTextStyle: { color: '#8b9cb3' },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#2d3f54', type: 'dashed' } },
      axisLabel: { color: '#8b9cb3' },
    },
    series: [
      {
        name: '优化前',
        type: 'bar',
        data: initialData,
        itemStyle: { color: '#64748b', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 36,
        barGap: '30%',
      },
      {
        name: '优化后',
        type: 'bar',
        data: optimizedData,
        itemStyle: { color: '#4ade80', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 36,
      },
    ],
  }
})

const improveOption = computed(() => {
  const items = METRICS.map((m) => {
    const init = initialScores.value[m.key]
    const opt = optimizedScores.value[m.key]
    return {
      name: m.name,
      value: +calcImprovement(init, opt).toFixed(1),
    }
  }).sort((a, b) => b.value - a.value)

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1e2a3a',
      borderColor: '#2d3f54',
      textStyle: { color: '#e8edf4' },
      formatter: (params) => {
        const p = params[0]
        return `${p.name}<br/>提升幅度: <strong>${p.value >= 0 ? '+' : ''}${p.value}%</strong>`
      },
    },
    grid: { left: '3%', right: '8%', bottom: '4%', top: '4%', containLabel: true },
    xAxis: {
      type: 'value',
      name: '变化率 (%)',
      nameTextStyle: { color: '#8b9cb3' },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#2d3f54', type: 'dashed' } },
      axisLabel: { color: '#8b9cb3', formatter: '{value}%' },
    },
    yAxis: {
      type: 'category',
      data: items.map((i) => i.name),
      axisLine: { lineStyle: { color: '#2d3f54' } },
      axisLabel: { color: '#8b9cb3' },
    },
    series: [
      {
        type: 'bar',
        data: items.map((i) => ({
          value: i.value,
          itemStyle: {
            color: i.value >= 0 ? '#4ade80' : '#ef4444',
            borderRadius: [0, 4, 4, 0],
          },
        })),
        barMaxWidth: 22,
        label: {
          show: true,
          position: 'right',
          color: '#8b9cb3',
          fontSize: 11,
          formatter: (p) => `${p.value >= 0 ? '+' : ''}${p.value}%`,
        },
      },
    ],
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

.chart-bar {
  height: 280px;
  width: 100%;
}

.improvement-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.improvement-section h4 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-secondary);
}

.chart-improve {
  height: 200px;
  width: 100%;
}
</style>
