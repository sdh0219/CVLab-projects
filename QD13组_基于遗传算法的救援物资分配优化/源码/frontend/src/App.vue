<template>
  <div class="app">
    <header class="header">
      <div class="header-content">
        <div class="brand">
          <span class="brand-icon">🚨</span>
          <div>
            <h1>救援物资分配优化可视化</h1>
            <p>基于遗传算法的河南洪涝灾害应急物资调度 · 基准案例与多场景模拟分析</p>
          </div>
        </div>
        <div class="header-actions">
          <div v-if="datasets.length > 1" class="dataset-tabs">
            <button
              v-for="ds in datasets"
              :key="ds.id"
              class="tab-btn"
              :class="{ active: ds.id === activeId }"
              @click="activeId = ds.id"
            >
              {{ ds.name }}
            </button>
          </div>
          <span v-if="currentData" class="update-time">数据更新: {{ currentData.generatedAt }}</span>
          <button
            class="btn-run"
            :disabled="running || loading"
            @click="handleRunAlgorithm(false)"
          >
            {{ running ? '运行中...' : '运行算法' }}
          </button>
          <button
            v-if="datasets.length > 1"
            class="btn-run secondary"
            :disabled="running || loading"
            @click="handleRunAlgorithm(true)"
          >
            运行当前数据集
          </button>
          <button class="btn-refresh" :disabled="loading || running" @click="loadData">
            {{ loading ? '加载中...' : '刷新数据' }}
          </button>
        </div>
      </div>
    </header>

    <main class="main">
      <RunConsole
        :visible="showConsole"
        :logs="runLogs"
        :running="running"
        :error="runError"
        @close="showConsole = false"
        @clear="runLogs = []"
      />

      <div v-if="loading" class="state-box">
        <div class="spinner"></div>
        <p>正在加载优化结果...</p>
      </div>

      <div v-else-if="error" class="state-box error">
        <p>{{ error }}</p>
        <p class="hint">请先运行算法生成数据，或点击上方「运行算法」按钮</p>
        <button class="btn-refresh" @click="loadData">重试</button>
      </div>

      <template v-else-if="currentData">
        <section v-if="currentData.summary?.scenario" class="section scenario-banner">
          <p>{{ currentData.summary.scenario }}</p>
          <div class="banner-tags">
            <span v-if="activeId === 'henan_disaster'" class="benchmark-tag">2021年河南极端暴雨 · 真实案例数据</span>
            <span v-else-if="isSimulatedDataset" class="sim-tag">规则模拟数据</span>
            <span class="algo-hint">
              遗传算法 · 种群 {{ currentData.algorithm?.pop_size }} ·
              {{ currentData.algorithm?.generations }} 代
            </span>
          </div>
        </section>

        <!-- ① 初始数据 -->
        <section class="section workflow-section">
          <SectionHeader
            step="1"
            title="初始数据"
            description="模型输入的受灾点需求、仓库库存与运力等基础数据"
          />
          <InitialDataPanel :input-data="inputData" />
        </section>

        <!-- ② 初始方案 -->
        <section class="section workflow-section">
          <SectionHeader
            step="2"
            title="初始方案"
            description="启发式生成的初始可行分配方案及其评价指标"
          />
          <InitialResultSummary :metrics="currentData.initialMetrics" />
          <AllocationHeatmap
            v-if="initialAllocationMatrix"
            :warehouse-names="currentData.warehouseNames"
            :point-names="currentData.pointNames"
            :allocation-matrix="initialAllocationMatrix"
            title="初始分配方案热力图"
            subtitle="各仓库向受灾点的初始物资分配总量（全部物资合计）"
          />
          <TransportPlanPanel
            v-if="initialTransportPlan.routeCount"
            :plan="initialTransportPlan"
            flow-title="初始方案调运流向"
            flow-subtitle="仓库向各受灾点的初始物资调运路径与运量"
            :show-flow-chart="showFlowChart"
          />
          <p v-else-if="!initialAllocationMatrix" class="missing-hint">暂无初始方案数据，请重新运行 export_for_frontend.py 导出</p>
        </section>

        <!-- ③ 遗传算法迭代过程 -->
        <section class="section workflow-section">
          <SectionHeader
            step="3"
            title="遗传算法迭代过程"
            description="选择、交叉、变异与局部搜索驱动的多代优化过程"
          />
          <div class="algo-params">
            <span>种群大小 {{ currentData.algorithm?.pop_size }}</span>
            <span>迭代代数 {{ currentData.algorithm?.generations }}</span>
            <span>变异率 {{ currentData.algorithm?.mutation_rate }}</span>
            <span>迭代记录 {{ currentData.fitnessHistory?.length ?? 0 }} 代</span>
          </div>
          <FitnessChart
            :fitness-history="currentData.fitnessHistory"
            :initial-fitness="currentData.initialFitness"
            :final-fitness="currentData.finalFitness"
          />
        </section>

        <!-- ④ 优化后分配方案 -->
        <section class="section workflow-section">
          <SectionHeader
            step="4"
            title="优化后分配方案"
            description="遗传算法收敛后的最优分配方案及与初始方案的对比分析"
          />
          <OptimizationResultSummary
            :summary="currentData.summary"
            :initial-metrics="currentData.initialMetrics"
            :optimized-metrics="currentData.optimizedMetrics"
            :initial-fitness="currentData.initialFitness"
            :final-fitness="currentData.finalFitness"
            :transport-plan="optimizedTransportPlan"
          />
          <div class="charts-row">
            <SatisfactionChart
              :point-names="currentData.pointNames"
              :initial-satisfaction="currentData.initialMetrics.detailed_satisfaction"
              :optimized-satisfaction="currentData.optimizedMetrics.detailed_satisfaction"
            />
            <MetricsRadar
              :initial-metrics="currentData.initialMetrics"
              :optimized-metrics="currentData.optimizedMetrics"
            />
          </div>
          <AllocationHeatmap
            :warehouse-names="currentData.warehouseNames"
            :point-names="currentData.pointNames"
            :allocation-matrix="currentData.allocationMatrix"
            title="优化后分配方案热力图"
            subtitle="各仓库向受灾点的优化后物资分配总量（全部物资合计）"
          />
          <TransportPlanPanel
            v-if="optimizedTransportPlan.routeCount"
            :plan="optimizedTransportPlan"
            flow-title="优化后调运流向"
            flow-subtitle="遗传算法优化后的仓库→受灾点物资调运路径与运量"
            :show-flow-chart="showFlowChart"
          />
        </section>

        <section class="section detail-table">
          <h3>各受灾点详细满足率对比（{{ currentData.pointNames.length }} 个）</h3>
          <table>
            <thead>
              <tr>
                <th>受灾点</th>
                <th>初始方案满足率</th>
                <th>优化后满足率</th>
                <th>提升幅度</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in visiblePointRows" :key="`${activeId}-${row.name}-${row.index}`">
                <td>{{ row.name }}</td>
                <td>{{ currentData.initialMetrics.detailed_satisfaction[row.index].toFixed(2) }}%</td>
                <td class="highlight">{{ currentData.optimizedMetrics.detailed_satisfaction[row.index].toFixed(2) }}%</td>
                <td :class="deltaClass(row.index)">
                  {{ deltaText(row.index) }}
                </td>
              </tr>
            </tbody>
          </table>
          <button
            v-if="currentData.pointNames.length > pointTableLimit"
            class="toggle-btn"
            @click="showAllPoints = !showAllPoints"
          >
            {{ showAllPoints ? '收起' : `展开全部 ${currentData.pointNames.length} 个受灾点` }}
          </button>
        </section>
      </template>
    </main>

    <footer class="footer">
      <p>项目13 · 基于遗传算法的救援物资分配优化 · Vue 3 + ECharts 可视化前端</p>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchResults, getDatasetById, DATASET_ORDER, buildInputDataFallback, getTransportPlan, runOptimization } from '@/api/dataService'
import SectionHeader from '@/components/SectionHeader.vue'
import InitialDataPanel from '@/components/InitialDataPanel.vue'
import InitialResultSummary from '@/components/InitialResultSummary.vue'
import OptimizationResultSummary from '@/components/OptimizationResultSummary.vue'
import TransportPlanPanel from '@/components/TransportPlanPanel.vue'
import SatisfactionChart from '@/components/SatisfactionChart.vue'
import FitnessChart from '@/components/FitnessChart.vue'
import AllocationHeatmap from '@/components/AllocationHeatmap.vue'
import MetricsRadar from '@/components/MetricsRadar.vue'
import RunConsole from '@/components/RunConsole.vue'

const payload = ref(null)
const activeId = ref(null)
const loading = ref(true)
const error = ref(null)
const running = ref(false)
const runLogs = ref([])
const runError = ref(null)
const showConsole = ref(false)
const showAllPoints = ref(false)
const pointTableLimit = 15

const datasets = computed(() => payload.value?.datasets || [])
const isSimulatedDataset = computed(() =>
  activeId.value === 'dataset_01_large_scale' ||
  activeId.value === 'dataset_02_complex_scenario'
)
const currentData = computed(() => {
  if (!payload.value) return null
  return getDatasetById(payload.value, activeId.value)
})
const inputData = computed(() =>
  currentData.value ? buildInputDataFallback(currentData.value) : null
)
const initialAllocationMatrix = computed(() =>
  currentData.value?.initialAllocationMatrix || null
)
const initialTransportPlan = computed(() =>
  currentData.value ? getTransportPlan(currentData.value, 'initial') : { routeCount: 0 }
)
const optimizedTransportPlan = computed(() =>
  currentData.value ? getTransportPlan(currentData.value, 'optimized') : { routeCount: 0 }
)
const showFlowChart = computed(() =>
  (currentData.value?.pointNames?.length ?? 0) <= 20
)
const visiblePointRows = computed(() => {
  const names = currentData.value?.pointNames || []
  const indices = names.map((_, i) => i)
  const slice = showAllPoints.value ? indices : indices.slice(0, pointTableLimit)
  return slice.map((index) => ({ name: names[index], index }))
})

function defaultDatasetId(list) {
  for (const id of DATASET_ORDER) {
    if (list.some((d) => d.id === id)) return id
  }
  return list[0]?.id || null
}

async function loadData() {
  loading.value = true
  error.value = null
  try {
    payload.value = await fetchResults()
    if (!activeId.value) {
      activeId.value = defaultDatasetId(payload.value.datasets)
    }
    showAllPoints.value = false
  } catch (e) {
    error.value = e.message
    payload.value = null
  } finally {
    loading.value = false
  }
}

async function handleRunAlgorithm(currentOnly) {
  running.value = true
  runError.value = null
  runLogs.value = []
  showConsole.value = true

  const datasetIds = currentOnly && activeId.value ? [activeId.value] : undefined

  try {
    await runOptimization({
      datasetIds,
      onLog: (msg) => { runLogs.value.push(msg) },
    })
    await loadData()
  } catch (e) {
    runError.value = e.message
    if (!runLogs.value.length) {
      runLogs.value.push(`错误: ${e.message}\n`)
    }
  } finally {
    running.value = false
  }
}

function deltaText(i) {
  const before = currentData.value.initialMetrics.detailed_satisfaction[i]
  const after = currentData.value.optimizedMetrics.detailed_satisfaction[i]
  const delta = after - before
  return `${delta >= 0 ? '+' : ''}${delta.toFixed(2)}%`
}

function deltaClass(i) {
  const before = currentData.value.initialMetrics.detailed_satisfaction[i]
  const after = currentData.value.optimizedMetrics.detailed_satisfaction[i]
  const delta = after - before
  if (delta > 0) return 'improvement'
  if (delta < 0) return 'negative'
  return ''
}

onMounted(loadData)
</script>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  background: linear-gradient(135deg, #1a2332 0%, #0f1419 100%);
  border-bottom: 1px solid var(--border);
  padding: 20px 32px;
}

.header-content {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 16px;
}

.brand-icon {
  font-size: 36px;
}

.brand h1 {
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 2px;
}

.brand p {
  font-size: 13px;
  color: var(--text-secondary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.dataset-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tab-btn {
  padding: 8px 14px;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  border-color: var(--accent);
  color: var(--text-primary);
}

.tab-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.scenario-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 14px 18px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
  color: var(--text-secondary);
}

.banner-tags {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.algo-hint {
  font-size: 12px;
  color: var(--accent-light);
}

.benchmark-tag {
  color: #f59e0b;
  font-weight: 600;
}

.sim-tag {
  color: #60a5fa;
  font-weight: 600;
}

.update-time {
  font-size: 13px;
  color: var(--text-secondary);
}

.btn-refresh {
  padding: 8px 18px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-run {
  padding: 8px 18px;
  background: var(--success);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-run.secondary {
  background: transparent;
  border: 1px solid var(--success);
  color: var(--success);
}

.btn-run:hover:not(:disabled) {
  filter: brightness(1.1);
}

.btn-run:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-refresh:hover:not(:disabled) {
  background: var(--accent-light);
}

.btn-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.main {
  flex: 1;
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px 32px;
  width: 100%;
}

.workflow-section {
  padding-top: 8px;
}

.algo-params {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--text-secondary);
}

.algo-params span {
  padding: 6px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
}

.missing-hint {
  font-size: 13px;
  color: var(--warning);
  padding: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.section {
  margin-bottom: 24px;
}

.charts-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
  gap: 20px;
}

.state-box {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-secondary);
}

.state-box.error {
  color: var(--danger);
}

.state-box .hint {
  margin: 12px 0 20px;
  font-size: 14px;
  color: var(--text-secondary);
}

.state-box code {
  background: var(--bg-card);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 13px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.detail-table {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  overflow-x: auto;
}

.detail-table h3 {
  font-size: 16px;
  margin-bottom: 16px;
}

.toggle-btn {
  margin-top: 12px;
  padding: 6px 14px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--accent-light);
  font-size: 13px;
  cursor: pointer;
}

.toggle-btn:hover {
  border-color: var(--accent);
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

th, td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

th {
  color: var(--text-secondary);
  font-weight: 500;
}

td.highlight {
  color: var(--accent-light);
  font-weight: 600;
}

td.positive,
td.improvement {
  color: var(--improvement);
  font-weight: 600;
}

td.negative {
  color: var(--danger);
  font-weight: 600;
}

.footer {
  text-align: center;
  padding: 20px;
  border-top: 1px solid var(--border);
  font-size: 13px;
  color: var(--text-secondary);
}
</style>
