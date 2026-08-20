<template>
  <div class="transport-plan">
    <div class="plan-overview">
      <div class="overview-item">
        <span class="label">调运路线</span>
        <span class="value">{{ plan.routeCount }} 条</span>
      </div>
      <div class="overview-item">
        <span class="label">总调运量</span>
        <span class="value">{{ formatNum(plan.totalShipped) }}</span>
      </div>
      <div class="overview-item">
        <span class="label">参与仓库</span>
        <span class="value">{{ plan.warehouseSummary?.length ?? 0 }} 个</span>
      </div>
    </div>

    <div class="subsection">
      <h4>仓库运力调度</h4>
      <p class="hint">各储备库车辆使用情况及出库总量</p>
      <div class="warehouse-grid">
        <div
          v-for="wh in plan.warehouseSummary"
          :key="wh.name"
          class="warehouse-card"
        >
          <div class="wh-name">{{ wh.name }}</div>
          <div class="wh-stats">
            <span>出库 <strong>{{ formatNum(wh.totalShipped) }}</strong></span>
            <span>覆盖 <strong>{{ wh.destinationCount }}</strong> 个受灾点</span>
          </div>
          <div class="wh-vehicle">
            <span>车辆 {{ wh.vehiclesUsed }} / {{ wh.vehicles }} 辆</span>
            <div class="util-bar">
              <div
                class="util-fill"
                :style="{ width: `${Math.min(100, (wh.utilization || 0) * 100)}%` }"
              />
            </div>
          </div>
          <div class="wh-cap">单车容量 {{ formatNum(wh.vehicleCapacity) }} · 最大运力 {{ formatNum(wh.maxTransport) }}</div>
        </div>
      </div>
    </div>

    <TransportFlowChart
      v-if="showFlowChart"
      :routes="plan.routes"
      :title="flowTitle"
      :subtitle="flowSubtitle"
      :max-routes="flowMaxRoutes"
    />

    <div class="subsection">
      <div class="routes-header">
        <div>
          <h4>调运路线明细</h4>
          <p class="hint">仓库 → 受灾点：分物资调运量、距离、路况、预计运输时间与车次</p>
        </div>
        <input
          v-model="searchText"
          class="search-input"
          placeholder="搜索仓库或受灾点..."
        />
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>出发仓库</th>
              <th>目标受灾点</th>
              <th>物资明细</th>
              <th>合计</th>
              <th>距离(km)</th>
              <th>路况</th>
              <th>时间(h)</th>
              <th>预估车次</th>
              <th>运输成本</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(route, i) in visibleRoutes" :key="`${route.warehouseName}-${route.pointName}-${i}`">
              <td class="wh-cell">{{ route.warehouseName }}</td>
              <td class="pt-cell">{{ route.pointName }}</td>
              <td class="materials-cell">
                <span
                  v-for="m in route.materials"
                  :key="m.name"
                  class="material-tag"
                >
                  {{ m.name }} {{ formatNum(m.amount) }}
                </span>
              </td>
              <td class="highlight">{{ formatNum(route.totalAmount) }}</td>
              <td>{{ route.distance }}</td>
              <td>
                <span class="road-badge" :class="roadClass(route.roadLabel)">
                  {{ route.roadLabel }} ({{ route.roadCondition }})
                </span>
              </td>
              <td>{{ route.transportTime }}</td>
              <td>{{ route.estimatedTrips }} 车</td>
              <td>{{ formatNum(route.transportCost) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <button
        v-if="filteredRoutes.length > defaultLimit"
        class="toggle-btn"
        @click="showAllRoutes = !showAllRoutes"
      >
        {{ showAllRoutes ? '收起' : `展开全部 ${filteredRoutes.length} 条路线` }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import TransportFlowChart from '@/components/TransportFlowChart.vue'

const props = defineProps({
  plan: { type: Object, required: true },
  flowTitle: { type: String, default: '物资调运流向图' },
  flowSubtitle: { type: String, default: '' },
  showFlowChart: { type: Boolean, default: true },
  flowMaxRoutes: { type: Number, default: 20 },
})

const defaultLimit = 15
const showAllRoutes = ref(false)
const searchText = ref('')

const filteredRoutes = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  if (!q) return props.plan.routes || []
  return (props.plan.routes || []).filter(
    (r) =>
      r.warehouseName.toLowerCase().includes(q) ||
      r.pointName.toLowerCase().includes(q)
  )
})

const visibleRoutes = computed(() =>
  showAllRoutes.value ? filteredRoutes.value : filteredRoutes.value.slice(0, defaultLimit)
)

function formatNum(n) {
  if (n == null) return '-'
  return Number(n).toLocaleString('zh-CN')
}

function roadClass(label) {
  if (label === '通畅') return 'road-good'
  if (label === '一般') return 'road-mid'
  return 'road-bad'
}
</script>

<style scoped>
.transport-plan {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-top: 16px;
}

.plan-overview {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
}

.overview-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  min-width: 120px;
}

.overview-item .label {
  font-size: 12px;
  color: var(--text-secondary);
}

.overview-item .value {
  font-size: 18px;
  font-weight: 700;
}

.subsection {
  margin-bottom: 20px;
}

.subsection h4 {
  font-size: 15px;
  margin-bottom: 4px;
}

.hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.warehouse-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}

.warehouse-card {
  padding: 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.wh-name {
  font-weight: 600;
  margin-bottom: 8px;
}

.wh-stats {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.wh-stats strong {
  color: var(--text-primary);
}

.wh-vehicle {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.util-bar {
  height: 6px;
  background: var(--border);
  border-radius: 3px;
  margin-top: 6px;
  overflow: hidden;
}

.util-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  transition: width 0.3s;
}

.wh-cap {
  font-size: 11px;
  color: var(--text-secondary);
}

.routes-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.search-input {
  padding: 8px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 13px;
  min-width: 200px;
}

.table-scroll {
  overflow-x: auto;
  max-height: 420px;
  overflow-y: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th, td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}

th {
  color: var(--text-secondary);
  font-weight: 500;
  position: sticky;
  top: 0;
  background: var(--bg-card);
  z-index: 1;
}

.wh-cell {
  font-weight: 600;
  color: var(--accent-light);
  white-space: nowrap;
}

.pt-cell {
  white-space: nowrap;
}

.materials-cell {
  min-width: 160px;
}

.material-tag {
  display: inline-block;
  padding: 2px 8px;
  margin: 2px 4px 2px 0;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
}

td.highlight {
  color: var(--improvement);
  font-weight: 600;
  white-space: nowrap;
}

.road-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
}

.road-good {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.road-mid {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.road-bad {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.toggle-btn {
  margin-top: 10px;
  padding: 6px 12px;
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
</style>
