<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <div class="page-kicker">EVACUATION COMMAND</div>
        <h2>群众转移管理</h2>
      </div>
      <div class="header-badge">容量调度 / 场所监测</div>
    </div>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value warning">2300+</div>
          <div class="stat-label">全市场所</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.total_shelters || 0 }}</div>
          <div class="stat-label">地图样本点</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value success">100+</div>
          <div class="stat-label">公园场所</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value info">1</div>
          <div class="stat-label">公开来源</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="evac-main-row module-main-row">
      <el-col :span="16">
        <el-card class="dashboard-card shelter-table-card">
          <template #header>避难场所</template>
          <el-table :data="shelters" stripe height="320" style="width: 100%">
            <el-table-column prop="shelter_name" label="场所名称" />
            <el-table-column prop="address" label="地址" show-overflow-tooltip />
            <el-table-column label="点位类型" width="120">
              <template #default>学校候选点</template>
            </el-table-column>
            <el-table-column label="公开属性" width="120">
              <template #default>公共设施</template>
            </el-table-column>
            <el-table-column label="数据来源" width="130">
              <template #default>OSM点位</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 'open' ? 'success' : row.status === 'full' ? 'danger' : 'info'" size="small">
                  {{ row.status === 'open' ? '开放' : row.status === 'full' ? '满员' : '关闭' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="dashboard-card usage-chart-card">
          <template #header>{{ hasCapacityData() ? '场所使用率' : '候选避难点位' }}</template>
          <div ref="chartRef" class="usage-chart"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="dashboard-card module-bottom-card">
      <template #header>转移方案生成</template>
      <el-form :inline="true">
        <el-form-item label="受灾人口">
          <el-input v-model.number="affectedPop" placeholder="输入受灾人口数" style="width: 150px" />
        </el-form-item>
        <el-form-item label="纬度">
          <el-input v-model.number="lat" placeholder="30.5728" style="width: 120px" />
        </el-form-item>
        <el-form-item label="经度">
          <el-input v-model.number="lon" placeholder="104.0668" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="generatePlan">生成方案</el-button>
        </el-form-item>
      </el-form>

      <div v-if="evacuationPlan" style="margin-top: 16px">
        <el-alert type="success" :closable="false">
          已根据输入位置查询候选安置点。{{ evacuationPlan.capacity_status || '公开报道显示成都全市应急避难场所2300余个，其中城市公园内100余个。' }}
        </el-alert>
        <el-table :data="evacuationPlan.plan" stripe style="width: 100%; margin-top: 12px">
          <el-table-column prop="shelter_name" label="避难场所" />
          <el-table-column label="建议用途" width="280" show-overflow-tooltip>
            <template #default="{ row }">{{ row.suggestion || '就近临时安置' }}</template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'
import { getShelters, getEvacuationStats, getEvacuationPlan } from '../api'

const shelters = ref([])
const stats = ref({})
const evacuationPlan = ref(null)
const chartRef = ref(null)
const affectedPop = ref(12000)
const lat = ref(30.5728)
const lon = ref(104.0668)

function hasCapacityData() {
  return shelters.value.some(s => Number(s.max_capacity) > 0)
}

async function loadData() {
  try {
    const [sheltersRes, statsRes] = await Promise.all([
      getShelters(),
      getEvacuationStats()
    ])
    shelters.value = sheltersRes.data
    stats.value = statsRes.data

    if (chartRef.value) {
      const chart = echarts.init(chartRef.value)
      const hasCapacity = sheltersRes.data.some(s => Number(s.max_capacity) > 0)
      chart.setOption(buildShelterChartOption(sheltersRes.data, hasCapacity))
    }
  } catch (e) {
    console.error('加载转移数据失败:', e)
  }
}

function buildShelterChartOption(data, hasCapacity) {
  const base = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { top: 48, bottom: 42, left: 142, right: 18, containLabel: false },
    xAxis: {
      type: 'value',
      min: 0,
      max: 1,
      splitNumber: 1,
      axisLabel: {
        color: '#a0cfff',
        margin: 10,
        formatter: value => Number(value) === 0 || Number(value) === 1 ? value : ''
      },
      axisLine: { lineStyle: { color: 'rgba(108, 183, 255, 0.35)' } },
      splitLine: { lineStyle: { color: 'rgba(80, 183, 255, 0.13)' } }
    },
    yAxis: {
      type: 'category',
      data: data.map(s => s.shelter_name),
      axisLabel: {
        color: '#c7e8ff',
        fontSize: 11,
        width: 128,
        overflow: 'truncate',
        formatter: value => value.length > 11 ? `${value.slice(0, 11)}...` : value
      },
      axisLine: { lineStyle: { color: 'rgba(108, 183, 255, 0.35)' } },
      axisTick: { show: false }
    }
  }

  if (!hasCapacity) {
    return {
      ...base,
      tooltip: {
        ...base.tooltip,
        formatter: params => `${params[0].name}<br/>候选避难点位`
      },
      legend: {
        top: 0,
        right: 6,
        itemWidth: 12,
        itemHeight: 8,
        itemGap: 14,
        textStyle: { color: '#c7e8ff', fontSize: 12 },
        data: ['候选点位']
      },
      xAxis: {
        ...base.xAxis,
        max: 1,
        axisLabel: { show: false },
        axisTick: { show: false },
        axisLine: { show: false },
        splitLine: { show: false }
      },
      series: [{
        name: '候选点位',
        type: 'bar',
        barWidth: 16,
        data: data.map(() => 1),
        itemStyle: { color: '#38a2ff', borderRadius: 2 }
      }]
    }
  }

  return {
    ...base,
    legend: {
      top: 0,
      right: 6,
      itemWidth: 12,
      itemHeight: 8,
      itemGap: 14,
      textStyle: { color: '#c7e8ff', fontSize: 12 },
      data: ['已使用', '可用']
    },
    series: [
      {
        name: '已使用',
        type: 'bar',
        stack: 'total',
        barWidth: 16,
        data: data.map(s => s.current_occupancy),
        itemStyle: { color: '#38a2ff', borderRadius: [2, 0, 0, 2] }
      },
      {
        name: '可用',
        type: 'bar',
        stack: 'total',
        barWidth: 16,
        data: data.map(s => s.max_capacity - s.current_occupancy),
        itemStyle: { color: '#63d13b', borderRadius: [0, 2, 2, 0] }
      }
    ]
  }
}

async function generatePlan() {
  try {
    const res = await getEvacuationPlan({
      affected_population: affectedPop.value,
      latitude: lat.value,
      longitude: lon.value
    })
    evacuationPlan.value = res.data
  } catch (e) {
    console.error('生成方案失败:', e)
  }
}

onMounted(async () => {
  await loadData()
  await generatePlan()
})
</script>

<style scoped>
.page-container {
  min-height: 100%;
  padding: 22px;
  background:
    linear-gradient(rgba(80, 180, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(80, 180, 255, 0.035) 1px, transparent 1px),
    radial-gradient(circle at 76% 8%, rgba(0, 212, 255, 0.16), transparent 28%),
    #07111f;
  background-size: 28px 28px, 28px 28px, auto, auto;
}

.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-kicker {
  color: #77caff;
  font-size: 12px;
  letter-spacing: 2px;
  margin-bottom: 4px;
}

.page-header h2 {
  color: #e8fbff;
  font-size: 24px;
  text-shadow: 0 0 14px rgba(0, 212, 255, 0.38);
}

.header-badge {
  padding: 8px 12px;
  border: 1px solid rgba(80, 183, 255, 0.24);
  border-radius: 8px;
  color: #bce6ff;
  background: rgba(8, 28, 50, 0.78);
}

.stats-row {
  margin-bottom: 22px;
}

.stat-card {
  position: relative;
  overflow: hidden;
  text-align: center;
  background: linear-gradient(180deg, rgba(16, 45, 76, 0.94), rgba(8, 23, 41, 0.96));
  border: 1px solid rgba(80, 183, 255, 0.2);
  border-radius: 8px;
  box-shadow: 0 16px 30px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.stat-card::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, rgba(0, 212, 255, 0.1), transparent 42%, rgba(91, 255, 175, 0.06));
  pointer-events: none;
}

.stat-card :deep(.el-card__body) {
  position: relative;
  padding: 18px 16px;
}

.stat-value { font-size: 32px; font-weight: bold; color: #66ddff; }
.stat-value.compact { font-size: 25px; line-height: 1.2; white-space: nowrap; }
.stat-value.warning { color: #e6a23c; }
.stat-value.success { color: #67c23a; }
.stat-value.info { color: #409eff; }
.stat-label { color: #a0cfff; margin-top: 8px; }

.evac-main-row {
  align-items: stretch;
}

.dashboard-card {
  height: 100%;
  background: linear-gradient(180deg, rgba(16, 45, 76, 0.94), rgba(8, 23, 41, 0.96));
  border: 1px solid rgba(80, 183, 255, 0.22);
  border-radius: 8px;
  box-shadow: 0 18px 34px rgba(0, 0, 0, 0.22);
}

.dashboard-card :deep(.el-card__header) {
  border-bottom: 1px solid rgba(80, 183, 255, 0.18);
  color: #dff7ff;
  font-weight: 700;
}

.dashboard-card :deep(.el-card__body) {
  padding: 18px 20px;
}

.page-container .module-main-row .usage-chart {
  height: 354px !important;
}

.page-container .module-main-row .usage-chart-card {
  height: 432px !important;
  min-height: 432px;
}

.shelter-table-card :deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: rgba(8, 26, 45, 0.68);
  --el-table-header-bg-color: rgba(12, 42, 70, 0.96);
  --el-table-row-hover-bg-color: rgba(0, 159, 255, 0.12);
  --el-table-border-color: rgba(80, 183, 255, 0.12);
  color: #d8ecff;
  background: transparent;
}

.shelter-table-card :deep(.el-table th.el-table__cell) {
  color: #a9d9ff;
  font-weight: 700;
}

.shelter-table-card :deep(.el-table tr),
.shelter-table-card :deep(.el-table td.el-table__cell) {
  background: rgba(8, 26, 45, 0.68);
}

.shelter-table-card :deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: rgba(12, 42, 70, 0.62);
}

.shelter-table-card :deep(.el-table td.el-table__cell) {
  border-bottom-color: rgba(80, 183, 255, 0.1);
}

.shelter-table-card :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: rgba(0, 159, 255, 0.14);
}

.shelter-table-card :deep(.el-table__inner-wrapper::before) {
  background-color: rgba(80, 183, 255, 0.14);
}
</style>
