<template>
  <div class="page-container">
    <div class="page-header">
      <h2>灾情态势</h2>
    </div>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value danger">{{ stats.total_events || 0 }}</div>
          <div class="stat-label">灾害事件总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.events_by_type?.extreme_weather || 0 }}</div>
          <div class="stat-label">极端天气案例</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value warning">{{ Object.keys(stats.events_by_type || {}).length }}</div>
          <div class="stat-label">灾害类型</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value info">{{ riskLessons.length }}</div>
          <div class="stat-label">复盘短板</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="module-main-row">
      <el-col :span="16">
        <el-card class="dashboard-card disaster-list-card">
          <template #header>灾情列表</template>
          <el-table :data="disasters" stripe style="width: 100%">
            <el-table-column prop="event_name" label="事件名称" />
            <el-table-column prop="disaster_type" label="灾害类型" width="100">
              <template #default="{ row }">
                {{ typeMap[row.disaster_type] || row.disaster_type }}
              </template>
            </el-table-column>
            <el-table-column prop="warning_level" label="预警等级" width="100">
              <template #default="{ row }">
                <el-tag :type="getWarningType(row.warning_level)" size="small">
                  {{ row.warning_level }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="response_level" label="响应等级" width="100" />
            <el-table-column label="公开事实" show-overflow-tooltip>
              <template #default="{ row }">{{ cleanDescription(row.description) }}</template>
            </el-table-column>
          </el-table>
          <div class="disaster-inline-summary">
            <div><strong>{{ disasters.filter(d => d.disaster_type === 'extreme_weather').length }}</strong><span>极端天气</span></div>
            <div><strong>{{ disasters.filter(d => d.warning_level === 'red' || d.warning_level === 'orange').length }}</strong><span>高等级预警</span></div>
            <div><strong>0</strong><span>虚构指标</span></div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="dashboard-card">
          <template #header>灾害类型分布</template>
          <div ref="chartRef" style="height: 300px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="module-extra-row">
      <el-col :span="16">
        <el-card class="dashboard-card">
          <template #header>历史灾情复盘</template>
          <div class="event-cards">
            <div v-for="item in disasters.slice(0, 5)" :key="item.id" class="event-card">
              <div class="event-card-head">
                <strong>{{ item.event_name }}</strong>
                <el-tag :type="getWarningType(item.warning_level)" size="small">{{ item.warning_level }}</el-tag>
              </div>
              <p>{{ cleanDescription(item.description) }}</p>
              <div class="event-meta">
                <span>{{ typeMap[item.disaster_type] || item.disaster_type }}</span>
                <span>响应 {{ item.response_level || 'IV' }} 级</span>
                <span>{{ item.warning_level }} 预警</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="dashboard-card">
          <template #header>历史短板纠偏</template>
          <div class="response-steps">
            <div v-for="(item, index) in riskLessons" :key="item.label" class="step-item">
              <b>{{ String(index + 1).padStart(2, '0') }}</b>
              <span>{{ item.label }}</span>
              <small>{{ item.action }}</small>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'
import { getDisasters, getDisasterStats } from '../api'
import { riskLessons } from '../data/publicKnowledge'

const disasters = ref([])
const stats = ref({})
const chartRef = ref(null)

const typeMap = {
  flood: '洪涝',
  earthquake: '地震',
  forest_fire: '森林火灾',
  extreme_weather: '极端天气'
}

function getWarningType(level) {
  const map = { red: 'danger', orange: 'warning', yellow: '', blue: 'info' }
  return map[level] || 'info'
}

function cleanDescription(description = '') {
  return description.split('数据来源：')[0].trim()
}

async function loadData() {
  try {
    const [disastersRes, statsRes] = await Promise.all([
      getDisasters(),
      getDisasterStats()
    ])
    disasters.value = disastersRes.data
    stats.value = statsRes.data

    // 初始化图表
    if (chartRef.value && statsRes.data.events_by_type) {
      const chart = echarts.init(chartRef.value)
      const data = Object.entries(statsRes.data.events_by_type)
        .filter(([, value]) => value > 0)
        .map(([name, value]) => ({ name: typeMap[name] || name, value }))
      chart.setOption({
        tooltip: { trigger: 'item' },
        series: [{
          type: 'pie',
          radius: '60%',
          data,
          label: { color: '#e0e6ed' }
        }]
      })
    }
  } catch (e) {
    console.error('加载灾情数据失败:', e)
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.page-container {
  padding: 20px;
}
.page-header {
  margin-bottom: 20px;
}
.page-header h2 {
  color: #00d4ff;
}
.stats-row {
  margin-bottom: 20px;
}
.stat-card {
  background: #0d2137;
  border: 1px solid #1a3a5c;
  text-align: center;
}
.stat-card :deep(.el-card__body) {
  padding: 20px;
}
.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #00d4ff;
}
.stat-value.danger { color: #f56c6c; }
.stat-value.warning { color: #e6a23c; }
.stat-value.info { color: #409eff; }
.stat-label {
  color: #a0cfff;
  margin-top: 8px;
}
.dashboard-card {
  background: #0d2137;
  border: 1px solid #1a3a5c;
}
.dashboard-card :deep(.el-card__header) {
  border-bottom: 1px solid #1a3a5c;
  color: #00d4ff;
}
.event-cards {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}
.event-card {
  min-height: 168px;
  padding: 12px;
  border: 1px solid rgba(80, 183, 255, 0.16);
  border-radius: 8px;
  background: rgba(8, 26, 45, 0.72);
}
.event-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #dff7ff;
}
.event-card p {
  color: #a9d9ff;
  line-height: 1.5;
  margin: 10px 0;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.event-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #8fb7d8;
  font-size: 12px;
}
.response-steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.step-item {
  display: grid;
  grid-template-columns: 36px 1fr;
  gap: 2px 10px;
  padding: 10px;
  border-left: 3px solid #4fd7ff;
  border-radius: 6px;
  background: rgba(8, 26, 45, 0.72);
}
.step-item b {
  grid-row: span 2;
  color: #66ddff;
}
.step-item span {
  color: #dff7ff;
  font-weight: 700;
}
.step-item small {
  color: #8fb7d8;
}
.disaster-inline-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 14px;
}
.disaster-inline-summary div {
  padding: 12px;
  border: 1px solid rgba(80, 183, 255, 0.14);
  border-radius: 8px;
  background: rgba(8, 26, 45, 0.72);
}
.disaster-inline-summary strong {
  display: block;
  color: #66ddff;
  font-size: 22px;
}
.disaster-inline-summary span {
  color: #8fb7d8;
  font-size: 12px;
}
.disaster-list-card :deep(.el-table) {
  height: 210px !important;
}
</style>
