<template>
  <div class="page-container">
    <div class="page-header">
      <h2>救援力量部署</h2>
    </div>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.total_teams || 0 }}</div>
          <div class="stat-label">救援队伍总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value success">{{ stats.available_teams || 0 }}</div>
          <div class="stat-label">可调度队伍</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ publicTypeCount(stats.by_type) }}</div>
          <div class="stat-label">公开资源类型</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value info">{{ publicSourceCount }}</div>
          <div class="stat-label">数据来源</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="module-main-row">
      <el-col :span="16">
        <el-card class="dashboard-card">
          <template #header>救援队伍列表</template>
          <el-table :data="teams" stripe style="width: 100%">
            <el-table-column prop="team_name" label="队伍名称" />
            <el-table-column prop="team_type" label="类型" width="80" />
            <el-table-column label="公开属性" width="110">
              <template #default="{ row }">{{ row.team_type }}点位</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'available' ? 'success' : 'warning'" size="small">
                  {{ row.status === 'available' ? '待命' : '已派出' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="equipment" label="数据说明" show-overflow-tooltip>
              <template #default="{ row }">
                {{ formatEquipment(row.equipment) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="dashboard-card">
          <template #header>队伍类型分布</template>
          <div ref="chartRef" style="height: 300px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="dashboard-card module-summary-card">
      <template #header>力量构成摘要</template>
      <div class="force-summary">
        <div v-for="(count, type) in stats.by_type || {}" :key="type" class="force-card">
          <span>{{ type }}</span>
          <strong>{{ count }}</strong>
          <small>{{ type === '消防' ? '抢险救援与排涝' : type === '医疗' ? '伤员救治与转运' : type === '无人机' ? '空中侦察巡检' : '人员物资运输' }}</small>
        </div>
      </div>
    </el-card>

    <el-card class="dashboard-card module-bottom-card">
      <template #header>最近救援力量计算</template>
      <el-form :inline="true">
        <el-form-item label="纬度">
          <el-input v-model="searchLat" placeholder="30.5728" style="width: 120px" />
        </el-form-item>
        <el-form-item label="经度">
          <el-input v-model="searchLon" placeholder="104.0668" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="searchNearest">查询最近队伍</el-button>
        </el-form-item>
      </el-form>
      <el-table v-if="nearestTeams.length > 0" :data="nearestTeams" stripe style="width: 100%; margin-top: 12px">
        <el-table-column prop="team_name" label="队伍名称" />
        <el-table-column prop="team_type" label="类型" width="80" />
        <el-table-column prop="distance_km" label="距离(km)" width="100" />
        <el-table-column prop="eta_hours" label="预计到达(h)" width="120" />
        <el-table-column label="公开属性" width="110">
          <template #default="{ row }">{{ row.team_type }}点位</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'
import { getRescueTeams, getRescueStats, getNearestRescue } from '../api'

const teams = ref([])
const stats = ref({})
const nearestTeams = ref([])
const chartRef = ref(null)
const searchLat = ref('30.5728')
const searchLon = ref('104.0668')
const publicSourceCount = 1

function publicTypeCount(byType = {}) {
  return Object.values(byType || {}).filter(value => Number(value) > 0).length
}

function formatEquipment(equipment) {
  if (!equipment) return ''
  if (equipment.source) return `${equipment.source}公开地图点位`
  return Object.entries(equipment).map(([k, v]) => `${k}×${v}`).join(', ')
}

async function loadData() {
  try {
    const [teamsRes, statsRes] = await Promise.all([
      getRescueTeams(),
      getRescueStats()
    ])
    teams.value = teamsRes.data
    stats.value = statsRes.data

    if (chartRef.value && statsRes.data.by_type) {
      const chart = echarts.init(chartRef.value)
      const data = Object.entries(statsRes.data.by_type).map(([name, value]) => ({ name, value }))
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
    console.error('加载救援数据失败:', e)
  }
}

async function searchNearest() {
  try {
    const res = await getNearestRescue({
      latitude: parseFloat(searchLat.value),
      longitude: parseFloat(searchLon.value),
      limit: 5
    })
    nearestTeams.value = res.data
  } catch (e) {
    console.error('查询失败:', e)
  }
}

onMounted(async () => {
  await loadData()
  searchNearest()
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
.stat-value.info { color: #409eff; }
.stat-label { color: #a0cfff; margin-top: 8px; }
.dashboard-card { background: #0d2137; border: 1px solid #1a3a5c; }
.dashboard-card :deep(.el-card__header) { border-bottom: 1px solid #1a3a5c; color: #00d4ff; }
.force-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.force-card {
  padding: 12px;
  border: 1px solid rgba(80, 183, 255, 0.16);
  border-radius: 8px;
  background: rgba(8, 26, 45, 0.72);
}
.force-card span {
  color: #a9d9ff;
}
.force-card strong {
  display: block;
  color: #66ddff;
  font-size: 26px;
  margin: 6px 0;
}
.force-card small {
  color: #8fb7d8;
}
</style>
