<template>
  <div class="page-container">
    <div class="page-header">
      <h2>物资调度管理</h2>
    </div>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">15+</div>
          <div class="stat-label">粮油储备天</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value success">3</div>
          <div class="stat-label">猪肉储备天</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value warning">{{ materials.length || 0 }}</div>
          <div class="stat-label">公开目录项</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value info">{{ Object.keys(stats.by_type || {}).length }}</div>
          <div class="stat-label">物资类型</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="module-main-row">
      <el-col :span="16">
        <el-card class="dashboard-card">
          <template #header>公开物资目录</template>
          <el-table :data="materials" stripe style="width: 100%">
            <el-table-column prop="material_name" label="物资名称" />
            <el-table-column prop="material_type" label="类型" width="100" />
            <el-table-column label="保障属性" width="120">
              <template #default>应急目录</template>
            </el-table-column>
            <el-table-column label="公开状态" width="120">
              <template #default>公开可展示</template>
            </el-table-column>
            <el-table-column prop="unit" label="单位" width="80" />
            <el-table-column label="依据" show-overflow-tooltip>
              <template #default>公开保供指标与应急物资目录</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="dashboard-card">
          <template #header>公开目录分布</template>
          <div ref="chartRef" style="height: 300px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="dashboard-card module-bottom-card">
      <template #header>物资需求计算</template>
      <el-form :inline="true">
        <el-form-item label="受灾人口">
          <el-input v-model.number="affectedPop" placeholder="输入受灾人口数" style="width: 150px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="calcDemand">计算需求</el-button>
        </el-form-item>
      </el-form>
      <div v-if="demandResult" class="demand-summary">
        <div
          v-for="(item, name) in demandResult.demand"
          :key="name"
          class="demand-card"
        >
          <span>{{ name }}</span>
          <strong>{{ item.quantity }}{{ item.unit }}</strong>
          <small>{{ item.description }}</small>
        </div>
      </div>
      <el-descriptions v-if="demandResult" :column="2" border style="margin-top: 12px">
        <el-descriptions-item v-for="(item, name) in demandResult.demand" :key="name" :label="name">
          {{ item.quantity }} {{ item.unit }} ({{ item.description }})
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getMaterials, getMaterialStats, calculateDemand } from '../api'

const materials = ref([])
const stats = ref({})
const demandResult = ref(null)
const chartRef = ref(null)
const affectedPop = ref(12000)

async function loadData() {
  try {
    const [materialsRes, statsRes] = await Promise.all([
      getMaterials(),
      getMaterialStats()
    ])
    materials.value = materialsRes.data
    stats.value = statsRes.data

    if (chartRef.value) {
      const chart = echarts.init(chartRef.value)
      const data = materialsRes.data.map(m => ({ name: m.material_name, value: 1 }))
      chart.setOption({
        tooltip: {
          trigger: 'item',
          formatter: params => `${params.name}<br/>公开目录：已纳入`
        },
        series: [{
          type: 'pie',
          radius: '60%',
          data,
          label: { color: '#e0e6ed', fontSize: 10 }
        }]
      })
    }
  } catch (e) {
    console.error('加载物资数据失败:', e)
  }
}

async function calcDemand(silent = false) {
  try {
    const res = await calculateDemand({ affected_population: affectedPop.value })
    demandResult.value = res.data
    if (!silent) ElMessage.success('物资需求已计算')
  } catch (e) {
    console.error('计算失败:', e)
    if (!silent) ElMessage.error('计算失败，请检查后端服务')
  }
}

onMounted(async () => {
  await loadData()
  await calcDemand(true)
})
</script>

<style scoped>
.page-container { padding: 20px; }
.page-header { margin-bottom: 20px; }
.page-header h2 { color: #00d4ff; }
.stats-row { margin-bottom: 20px; }
.stat-card { background: #0d2137; border: 1px solid #1a3a5c; text-align: center; }
.stat-card :deep(.el-card__body) { padding: 20px; }
.stat-value { font-size: 32px; font-weight: bold; color: #00d4ff; }
.stat-value.compact { font-size: 25px; line-height: 1.2; white-space: nowrap; }
.stat-value.success { color: #67c23a; }
.stat-value.warning { color: #e6a23c; }
.stat-value.info { color: #409eff; }
.stat-label { color: #a0cfff; margin-top: 8px; }
.dashboard-card { background: #0d2137; border: 1px solid #1a3a5c; }
.dashboard-card :deep(.el-card__header) { border-bottom: 1px solid #1a3a5c; color: #00d4ff; }
.demand-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 12px;
}
.demand-card {
  padding: 12px;
  border: 1px solid rgba(80, 183, 255, 0.18);
  border-radius: 8px;
  background: rgba(8, 26, 45, 0.72);
}
.demand-card span {
  color: #a9d9ff;
  font-size: 13px;
}
.demand-card strong {
  display: block;
  color: #66ddff;
  font-size: 24px;
  margin: 6px 0;
}
.demand-card small {
  color: #8fb7d8;
}
</style>
