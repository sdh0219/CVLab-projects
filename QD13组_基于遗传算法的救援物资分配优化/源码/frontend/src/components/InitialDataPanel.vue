<template>
  <div class="initial-data">
    <div class="totals-row">
      <div v-for="item in totalItems" :key="item.label" class="total-chip">
        <span class="chip-label">{{ item.label }}</span>
        <span class="chip-value">{{ item.value }}</span>
      </div>
    </div>

    <div class="tables-grid">
      <div class="table-block">
        <h4>受灾点需求数据</h4>
        <p class="table-hint">各受灾点人口、紧急程度及各物资需求量</p>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>受灾点</th>
                <th>人口</th>
                <th>紧急度</th>
                <th v-for="mat in materialNames" :key="mat">{{ mat }}需求</th>
                <th>需求合计</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(point, i) in visiblePoints" :key="point.name">
                <td>{{ point.name }}</td>
                <td>{{ formatNum(point.population) }}</td>
                <td>{{ point.urgency?.toFixed?.(2) ?? point.urgency }}</td>
                <td v-for="(d, mi) in point.demand" :key="mi">{{ formatNum(d) }}</td>
                <td class="highlight">{{ formatNum(rowSum(point.demand)) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <button
          v-if="disasterPoints.length > defaultLimit"
          class="toggle-btn"
          @click="showAllPoints = !showAllPoints"
        >
          {{ showAllPoints ? '收起' : `展开全部 ${disasterPoints.length} 个受灾点` }}
        </button>
      </div>

      <div class="table-block">
        <h4>仓库库存与运力</h4>
        <p class="table-hint">各仓库物资库存、车辆数及最大运输能力</p>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>仓库</th>
                <th>车辆数</th>
                <th>单车容量</th>
                <th>最大运力</th>
                <th v-for="mat in materialNames" :key="mat">{{ mat }}库存</th>
                <th>库存合计</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="wh in warehouses" :key="wh.name">
                <td>{{ wh.name }}</td>
                <td>{{ wh.vehicles }}</td>
                <td>{{ formatNum(wh.vehicleCapacity) }}</td>
                <td>{{ formatNum(wh.maxTransport) }}</td>
                <td v-for="(inv, mi) in wh.inventory" :key="mi">{{ formatNum(inv) }}</td>
                <td class="highlight">{{ formatNum(rowSum(wh.inventory)) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { formatNumber } from '@/api/dataService'

const props = defineProps({
  inputData: { type: Object, required: true },
})

const defaultLimit = 12
const showAllPoints = ref(false)

const materialNames = computed(() => props.inputData.materialNames || [])
const disasterPoints = computed(() => props.inputData.disasterPoints || [])
const warehouses = computed(() => props.inputData.warehouses || [])
const totals = computed(() => props.inputData.totals || {})

const visiblePoints = computed(() =>
  showAllPoints.value ? disasterPoints.value : disasterPoints.value.slice(0, defaultLimit)
)

const totalItems = computed(() => [
  { label: '受灾点', value: `${totals.value.disasterPointsCount ?? disasterPoints.value.length} 个` },
  { label: '仓库', value: `${totals.value.warehousesCount ?? warehouses.value.length} 个` },
  { label: '物资类型', value: `${totals.value.materialsCount ?? materialNames.value.length} 种` },
  { label: '受灾人口', value: formatNumber(totals.value.population ?? 0) },
  { label: '总需求量', value: formatNumber(totals.value.demand ?? 0) },
  { label: '总库存量', value: formatNumber(totals.value.inventory ?? 0) },
])

function formatNum(n) {
  if (n == null) return '-'
  return Number(n).toLocaleString('zh-CN')
}

function rowSum(arr) {
  return (arr || []).reduce((s, v) => s + Number(v), 0)
}
</script>

<style scoped>
.initial-data {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
}

.totals-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 20px;
}

.total-chip {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  min-width: 100px;
}

.chip-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.chip-value {
  font-size: 15px;
  font-weight: 600;
}

.tables-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
  gap: 20px;
}

.table-block h4 {
  font-size: 15px;
  margin-bottom: 4px;
}

.table-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.table-scroll {
  overflow-x: auto;
  max-height: 360px;
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
  white-space: nowrap;
}

th {
  color: var(--text-secondary);
  font-weight: 500;
  position: sticky;
  top: 0;
  background: var(--bg-card);
  z-index: 1;
}

td.highlight {
  color: var(--accent-light);
  font-weight: 600;
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
