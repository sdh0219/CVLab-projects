<template>
  <div class="dashboard-container">
    <!-- 顶部标题 -->
    <header class="dashboard-header">
      <div class="header-title">
        <div class="title-kicker">跨部门协同应急响应平台</div>
        <h1>AI应急指挥舱</h1>
      </div>
      <div class="header-info">
        <span class="status-dot"></span>
        <span>联动在线</span>
        <span>{{ currentTime }}</span>
        <el-tag type="danger" size="small" v-if="dashboardData.disaster?.active_events > 0">
          {{ dashboardData.disaster?.active_events }}个活跃事件
        </el-tag>
      </div>
    </header>

    <!-- 主内容区 -->
    <div class="dashboard-body">
      <!-- 左侧面板 -->
      <aside class="left-panel">
        <!-- 灾情统计 -->
        <div class="dashboard-card insight-card disaster-insight">
          <div class="card-title">灾情统计</div>
          <div class="stat-grid">
            <div class="stat-item">
              <div class="stat-value danger">{{ dashboardData.disaster?.total_events || 0 }}</div>
              <div class="stat-label">灾害事件</div>
            </div>
            <div class="stat-item">
              <div class="stat-value warning">{{ dashboardData.disaster?.active_events || 0 }}</div>
              <div class="stat-label">活跃事件</div>
            </div>
            <div class="stat-item">
              <div class="stat-value info">{{ dashboardData.roads?.total || 0 }}</div>
              <div class="stat-label">道路点位</div>
            </div>
          </div>
          <div ref="disasterChartRef" class="chart-container"></div>
        </div>

        <!-- 救援力量 -->
        <div class="dashboard-card insight-card rescue-insight">
          <div class="card-title">救援力量</div>
          <div class="stat-grid">
            <div class="stat-item">
              <div class="stat-value success">{{ rescueStats.total_teams || 0 }}</div>
              <div class="stat-label">总队伍</div>
            </div>
            <div class="stat-item">
              <div class="stat-value info">{{ rescueStats.available_teams || 0 }}</div>
              <div class="stat-label">可调度</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ publicTypeCount(rescueStats.by_type) }}</div>
              <div class="stat-label">资源类型</div>
            </div>
          </div>
          <div ref="rescueChartRef" class="chart-container"></div>
        </div>

        <!-- 气象预警 -->
        <div class="dashboard-card weather-card">
          <div class="card-title">气象预警</div>
          <div class="weather-list">
            <div v-for="w in weatherData" :key="w.id" class="weather-item">
              <span class="region">{{ w.region_name }}</span>
              <el-tag :type="getWarningType(w.warning_level)" size="small">
                {{ getWarningText(w.warning_level) }}
              </el-tag>
              <span class="detail">降雨{{ w.rainfall }}mm</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- 中间地图 -->
      <main class="center-panel">
        <div class="map-shell">
          <div class="map-container" ref="mapRef"></div>
          <div class="map-toolbar">
            <span>多源态势地图</span>
            <strong>灾情 / 队伍 / 避难 / 道路</strong>
          </div>
          <div class="map-legend">
            <span><i class="legend-dot disaster"></i>灾害点</span>
            <span><i class="legend-dot rescue"></i>救援队</span>
            <span><i class="legend-square shelter"></i>避难场所</span>
            <span><i class="legend-line road"></i>中断道路</span>
          </div>
        </div>
        <!-- 底部事件流 -->
        <div class="event-stream">
          <div class="stream-title">
            <span>实时事件</span>
            <em>LIVE INCIDENT FEED</em>
          </div>
          <div class="stream-list">
            <div v-for="(event, index) in eventStream" :key="index" class="stream-item">
              <span class="stream-time">{{ event.time }}</span>
              <el-tag :type="event.type" size="small">{{ event.tag }}</el-tag>
              <span class="stream-text">{{ event.text }}</span>
            </div>
          </div>
        </div>
      </main>

      <!-- 右侧面板 -->
      <aside class="right-panel">
        <!-- AI决策建议 -->
        <div class="dashboard-card ai-card">
          <div class="card-title">
            <el-icon><Cpu /></el-icon>
            AI决策建议
          </div>
          <div v-if="latestDecision" class="decision-content">
            <div class="decision-section">
              <div class="section-label">风险评估</div>
              <p>{{ latestDecision.risk_assessment?.assessment_summary || latestDecision.risk_assessment }}</p>
            </div>
            <div class="decision-section">
              <div class="section-label">响应建议</div>
              <p>{{ latestDecision.response_plan?.substring(0, 150) || '前往AI决策模块查看详细方案' }}</p>
            </div>
            <div class="decision-section">
              <div class="section-label">资源部署</div>
              <p>{{ latestDecision.resource_prediction?.prediction_summary || '资源预测待生成' }}</p>
            </div>
          </div>
          <div v-else class="empty-tip">暂无AI决策，前往AI决策模块生成</div>
        </div>

        <!-- 物资调度 -->
        <div class="dashboard-card material-card">
          <div class="card-title">物资调度</div>
          <div class="stat-grid">
            <div class="stat-item">
              <div class="stat-value">15+</div>
              <div class="stat-label">粮油储备天</div>
            </div>
            <div class="stat-item">
              <div class="stat-value success">{{ Object.keys(materialStats.by_type || {}).length }}</div>
              <div class="stat-label">物资类别</div>
            </div>
          </div>
          <div ref="materialChartRef" class="chart-container"></div>
        </div>

        <!-- 群众转移 -->
        <div class="dashboard-card transfer-card">
          <div class="card-title">群众转移</div>
          <div class="stat-grid">
            <div class="stat-item">
              <div class="stat-value warning">2300+</div>
              <div class="stat-label">全市场所</div>
            </div>
            <div class="stat-item">
              <div class="stat-value info">100+</div>
              <div class="stat-label">公园场所</div>
            </div>
          </div>
          <el-progress
            :percentage="knownPositive(evacuationStats.utilization_rate) ? evacuationStats.utilization_rate : 0"
            :color="customColors"
            :stroke-width="12"
            :show-text="false"
          />
          <div class="progress-label">当前地图候选点位：{{ evacuationStats.total_shelters || 0 }}处</div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import {
  getDisasterStats, getRescueStats, getMaterialStats,
  getEvacuationStats, getWeather, getAIDecisions, getDisasters,
  getRescueTeams, getShelters, getRoads
} from '../api'
import { historicalDisasterCases, riskLessons } from '../data/publicKnowledge'

const currentTime = ref('')
const dashboardData = ref({})
const rescueStats = ref({})
const materialStats = ref({})
const evacuationStats = ref({})
const weatherData = ref([])
const latestDecision = ref(null)
const eventStream = ref([])

const mapRef = ref(null)
const disasterChartRef = ref(null)
const rescueChartRef = ref(null)
const materialChartRef = ref(null)

let map = null
let timer = null
let disasterChart = null
let rescueChart = null
let materialChart = null

const customColors = [
  { color: '#00d4ff', percentage: 50 },
  { color: '#e6a23c', percentage: 80 },
  { color: '#f56c6c', percentage: 100 }
]

// 更新时间
function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN')
}

// 预警类型映射
function getWarningType(level) {
  const map = { red: 'danger', orange: 'warning', yellow: '', blue: 'info' }
  return map[level] || 'info'
}

function getWarningText(level) {
  const map = { red: '红色预警', orange: '橙色预警', yellow: '黄色预警', blue: '蓝色预警' }
  return map[level] || '未知'
}

function knownPositive(value) {
  return Number(value) > 0
}

function publicTypeCount(byType = {}) {
  return Object.values(byType).filter(value => Number(value) > 0).length
}

function translateDisasterType(type) {
  const map = {
    flood: '洪涝',
    extreme_weather: '极端天气',
    forest_fire: '森林火灾',
    rainstorm: '暴雨',
    storm: '强对流',
    fire: '火灾',
    earthquake: '地震',
    other: '其他'
  }
  return map[type] || type || '未分类'
}

function createMapPin(type, count = '') {
  return `
    <div class="beacon-marker beacon-${type}">
      <span class="beacon-halo"></span>
      <span class="beacon-core">${count ? `<b>${count}</b>` : ''}</span>
      <span class="beacon-base"></span>
    </div>
  `
}

// 初始化地图
function initMap() {
  map = L.map(mapRef.value, {
    center: [30.5728, 104.0668],
    zoom: 12,
    zoomControl: false
  })

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
  }).addTo(map)

  // 添加灾害点位
  addMapMarkers()
}

async function addMapMarkers() {
  try {
    // 灾害点位
    const disasters = await getDisasters()
    disasters.data.forEach(d => {
      const icon = L.divIcon({
        className: 'custom-marker',
        html: createMapPin('danger'),
        iconSize: [42, 52],
        iconAnchor: [21, 42],
        popupAnchor: [0, -40]
      })
      L.marker([d.latitude, d.longitude], { icon })
        .addTo(map)
        .bindPopup(`<b>${d.event_name}</b><br>${d.disaster_type}<br>公开事件记录`)
    })

    // 救援队伍
    const teams = await getRescueTeams()
    teams.data.forEach(t => {
      const icon = L.divIcon({
        className: 'custom-marker',
        html: createMapPin('success', t.member_count > 0 ? t.member_count : ''),
        iconSize: [42, 52],
        iconAnchor: [21, 42],
        popupAnchor: [0, -40]
      })
      L.marker([t.latitude, t.longitude], { icon })
        .addTo(map)
        .bindPopup(`<b>${t.team_name}</b><br>${t.team_type}<br>OpenStreetMap公开点位`)
    })

    // 避难场所
    const shelters = await getShelters()
    shelters.data.forEach(s => {
      const icon = L.divIcon({
        className: 'custom-marker',
        html: createMapPin('info'),
        iconSize: [42, 52],
        iconAnchor: [21, 42],
        popupAnchor: [0, -40]
      })
      L.marker([s.latitude, s.longitude], { icon })
        .addTo(map)
        .bindPopup(`<b>${s.shelter_name}</b><br>候选安置公共设施`)
    })

    // 道路中断
    const roads = await getRoads()
    roads.data.filter(r => r.status === 'blocked').forEach(r => {
      if (r.start_latitude && r.end_latitude) {
        L.polyline(
          [[r.start_latitude, r.start_longitude], [r.end_latitude, r.end_longitude]],
          { color: '#f56c6c', weight: 4, dashArray: '10, 10' }
        ).addTo(map).bindPopup(`<b>${r.road_name}</b><br>状态: 中断`)
      }
    })
  } catch (e) {
    console.error('加载地图标记失败:', e)
  }
}

// 初始化图表
function initCharts() {
  // 灾情类型分布图
  if (disasterChartRef.value) {
    disasterChart = echarts.init(disasterChartRef.value)
    disasterChart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['34%', '51%'],
        center: ['50%', '43%'],
        avoidLabelOverlap: true,
        data: [
          { value: 1, name: '洪涝' },
          { value: 1, name: '极端天气' },
          { value: 1, name: '森林火灾' }
        ],
        label: {
          color: '#d7efff',
          fontSize: 10,
          lineHeight: 14,
          formatter: '{b}'
        },
        labelLine: {
          length: 8,
          length2: 12,
          lineStyle: { color: 'rgba(160, 207, 255, 0.58)' }
        }
      }]
    })
  }

  // 救援力量分布
  if (rescueChartRef.value) {
    rescueChart = echarts.init(rescueChartRef.value)
    rescueChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { top: 10, bottom: 30, left: 42, right: 12 },
      xAxis: {
        type: 'category',
        data: ['消防', '医疗', '无人机', '车辆'],
        axisLabel: { color: '#a0cfff', fontSize: 10 }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#a0cfff' },
        splitLine: { lineStyle: { color: '#1a3a5c' } }
      },
      series: [{
        type: 'bar',
        data: [3, 3, 1, 1],
        itemStyle: { color: '#00d4ff' }
      }]
    })
  }

  // 物资库存
  if (materialChartRef.value) {
    materialChart = echarts.init(materialChartRef.value)
    materialChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { top: 4, bottom: 18, left: 4, right: 22, containLabel: true },
      xAxis: {
        type: 'value',
        min: 0,
        max: 1,
        splitNumber: 1,
        axisLabel: {
          show: false
        },
        axisTick: { show: false },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: 'rgba(80, 183, 255, 0.16)' } }
      },
      yAxis: {
        type: 'category',
        data: ['救生衣', '沙袋', '饮用水', '帐篷', '发电机'],
        axisLabel: { color: '#a0cfff', fontSize: 10 },
        axisTick: { show: false }
      },
      series: [{
        type: 'bar',
        barWidth: 10,
        data: [1, 1, 1, 1, 1],
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#00d4ff' },
            { offset: 1, color: '#67c23a' }
          ])
        }
      }]
    })
  }
}

function updateCharts(disasterStats, rescueData, materialData) {
  if (disasterChart) {
    const byType = disasterStats?.events_by_type || {}
    const data = Object.entries(byType)
      .filter(([, value]) => Number(value) > 0)
      .map(([name, value]) => ({ name: translateDisasterType(name), value }))
    disasterChart.setOption({
      series: [{ data: data.length ? data : [{ value: 1, name: '公开事件' }] }]
    })
  }

  if (rescueChart) {
    const byType = rescueData?.by_type || {}
    const entries = Object.entries(byType).filter(([, value]) => Number(value) > 0)
    rescueChart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: params => `${params[0].name}<br/>真实公开点位：${params[0].value}`
      },
      xAxis: { data: entries.map(([name]) => name) },
      series: [{ data: entries.map(([, value]) => value) }]
    })
  }

  if (materialChart) {
    const byType = materialData?.by_type || {}
    const entries = Object.entries(byType)
    materialChart.setOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: params => `${params[0].name}<br/>公开物资目录：${params[0].value}项`
      },
      xAxis: {
        min: 0,
        max: 1,
        splitNumber: 1,
        axisLabel: {
          show: false
        },
        axisTick: { show: false },
        axisLine: { show: false }
      },
      yAxis: { data: entries.map(([name]) => name) },
      series: [{
        data: entries.map(() => 1),
        label: { show: false }
      }]
    })
  }
}

// 加载数据
async function loadData() {
  try {
    const [disasterStats, disasters, rescue, material, evacuation, weather, roads, decisions] = await Promise.all([
      getDisasterStats(),
      getDisasters(),
      getRescueStats(),
      getMaterialStats(),
      getEvacuationStats(),
      getWeather(),
      getRoads(),
      getAIDecisions()
    ])

    const disasterList = Array.isArray(disasters.data) ? disasters.data : []
    const roadList = Array.isArray(roads.data) ? roads.data : []
    const activeEvents = disasterList.filter(d => ['I', 'II'].includes(d.response_level)).length

    dashboardData.value = {
      disaster: {
        total_events: disasterStats.data.total_events || disasterList.length,
        active_events: activeEvents
      },
      roads: {
        blocked: roadList.filter(r => r.status === 'blocked').length,
        total: roadList.length
      }
    }
    rescueStats.value = rescue.data
    materialStats.value = material.data
    evacuationStats.value = evacuation.data
    weatherData.value = weather.data
    updateCharts(disasterStats.data, rescue.data, material.data)
    generateEventStream({
      disasterList,
      rescueData: rescue.data,
      materialData: material.data,
      evacuationData: evacuation.data,
      weatherData: weather.data,
      roadList
    })

    // 加载最新AI决策
    if (decisions.data && decisions.data.length > 0) {
      latestDecision.value = decisions.data[0]
    } else {
      latestDecision.value = null
    }
  } catch (e) {
    console.error('加载数据失败:', e)
  }
}

// 生成真实公开数据接入事件流
function generateEventStream(payload = {}) {
  const now = new Date()
  const timeAt = minutes => new Date(now.getTime() - minutes * 60000).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
  const events = [
    {
      time: timeAt(2),
      type: 'info',
      tag: '气象',
      text: `接入Open-Meteo成都市中心城区实况，降雨${payload.weatherData?.[0]?.rainfall ?? 0}mm`
    },
    {
      time: timeAt(6),
      type: 'success',
      tag: '救援',
      text: `接入${payload.rescueData?.total_teams || 0}个OSM公开救援资源点位`
    },
    {
      time: timeAt(10),
      type: 'warning',
      tag: '安置',
      text: `成都公开报道显示全市应急避难场所2300余个，公园内100余个`
    },
    {
      time: timeAt(14),
      type: 'info',
      tag: '道路',
      text: `接入${payload.roadList?.length || 0}条成都公开道路点位，当前无中断发布`
    },
    {
      time: timeAt(18),
      type: 'info',
      tag: '物资',
      text: `成都公开保供指标：粮油15日以上供应量，猪肉不低于3日消费量`
    },
    {
      time: timeAt(22),
      type: 'danger',
      tag: '灾情',
      text: `导入${payload.disasterList?.length || 0}条公开灾情记录，并接入气象实况`
    }
  ]
  eventStream.value = events
}

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  loadData()
  initMap()
  initCharts()
  
  // 每10秒刷新数据（包括AI决策）
  setInterval(loadData, 10000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.dashboard-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background:
    linear-gradient(rgba(80, 180, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(80, 180, 255, 0.035) 1px, transparent 1px),
    radial-gradient(circle at 50% 24%, rgba(0, 131, 255, 0.18), transparent 34%),
    #07111f;
  background-size: 28px 28px, 28px 28px, auto, auto;
  overflow: hidden;
}

.dashboard-header {
  height: 72px;
  background: linear-gradient(90deg, rgba(9, 28, 48, 0.96) 0%, rgba(19, 58, 92, 0.92) 50%, rgba(9, 28, 48, 0.96) 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.48);
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.24);
}

.header-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.title-kicker {
  color: #7cc9ff;
  font-size: 12px;
  letter-spacing: 2px;
}

.dashboard-header h1 {
  color: #e8fbff;
  font-size: 24px;
  line-height: 1.1;
  text-shadow: 0 0 14px rgba(0, 212, 255, 0.42);
}

.header-info {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #c8e8ff;
  font-size: 13px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #35f5a7;
  box-shadow: 0 0 12px rgba(53, 245, 167, 0.9);
}

.dashboard-body {
  flex: 1;
  display: grid;
  grid-template-columns: 336px minmax(470px, 1fr) 336px;
  gap: 12px;
  padding: 14px 16px;
  overflow: hidden;
  min-height: 0;
}

.left-panel, .right-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px;
}

.center-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.map-shell {
  position: relative;
  flex: 1;
  min-height: 0;
  border-radius: 8px;
  border: 1px solid rgba(80, 183, 255, 0.24);
  overflow: hidden;
  background: #081727;
  box-shadow: inset 0 0 42px rgba(0, 212, 255, 0.12), 0 18px 36px rgba(0, 0, 0, 0.22);
}

.map-container {
  height: 100%;
  border-radius: 8px;
  overflow: hidden;
}

.map-toolbar,
.map-legend {
  position: absolute;
  z-index: 500;
  left: 14px;
  right: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  pointer-events: none;
}

.map-toolbar {
  top: 14px;
  padding: 10px 12px;
  border: 1px solid rgba(80, 183, 255, 0.22);
  border-radius: 8px;
  background: rgba(7, 20, 36, 0.78);
  color: #dff7ff;
  backdrop-filter: blur(8px);
}

.map-toolbar span {
  font-size: 15px;
  font-weight: 700;
}

.map-toolbar strong {
  color: #8ed8ff;
  font-size: 12px;
  font-weight: 500;
}

.map-legend {
  bottom: 14px;
  justify-content: center;
  gap: 14px;
  width: auto;
  margin: 0 auto;
  padding: 8px 12px;
  border: 1px solid rgba(80, 183, 255, 0.22);
  border-radius: 8px;
  background: rgba(7, 20, 36, 0.76);
  color: #d8edf8;
  font-size: 12px;
  backdrop-filter: blur(8px);
}

.map-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend-dot,
.legend-square {
  display: inline-block;
  width: 10px;
  height: 10px;
}

.legend-dot {
  border-radius: 50%;
}

.legend-dot.disaster { background: #ff3d4f; box-shadow: 0 0 10px rgba(255, 61, 79, 0.8); }
.legend-dot.rescue { background: #28e59b; box-shadow: 0 0 10px rgba(40, 229, 155, 0.8); }
.legend-square.shelter {
  background: #2aa7ff;
  border-radius: 50%;
  box-shadow: 0 0 10px rgba(42, 167, 255, 0.8);
}
.legend-line.road {
  width: 18px;
  height: 0;
  border-top: 2px dashed #f56c6c;
}

:deep(.custom-marker) {
  background: transparent;
  border: none;
}

:deep(.beacon-marker) {
  position: relative;
  width: 42px;
  height: 48px;
  transform: translateZ(0);
}

:deep(.beacon-core) {
  position: absolute;
  left: 10px;
  top: 4px;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  font-weight: 800;
  border: 2px solid rgba(255, 255, 255, 0.9);
  z-index: 2;
}

:deep(.beacon-core)::after {
  content: "";
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.92);
}

:deep(.beacon-core:not(:empty))::after {
  display: none;
}

:deep(.beacon-core b) {
  color: #fff;
  font-size: 9px;
  line-height: 1;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
}

:deep(.beacon-halo) {
  position: absolute;
  left: 3px;
  top: -3px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  filter: blur(9px);
  opacity: 0.86;
  z-index: 1;
}

:deep(.beacon-base) {
  position: absolute;
  left: 5px;
  bottom: 5px;
  width: 32px;
  height: 13px;
  border: 2px solid currentColor;
  border-radius: 50%;
  opacity: 0.85;
  box-shadow: 0 0 14px currentColor, inset 0 0 10px currentColor;
}

:deep(.beacon-base)::after {
  content: "";
  position: absolute;
  inset: 3px;
  border: 1px solid currentColor;
  border-radius: 50%;
  opacity: 0.65;
}

:deep(.beacon-danger) { color: #ff3d4f; }
:deep(.beacon-danger .beacon-core) {
  background: radial-gradient(circle at 35% 30%, #fff 0 8%, #ff6b78 9% 28%, #ff1730 72%);
  box-shadow: 0 0 18px rgba(255, 43, 63, 0.95);
}
:deep(.beacon-danger .beacon-halo) { background: rgba(255, 43, 63, 0.78); }

:deep(.beacon-success) { color: #26e59a; }
:deep(.beacon-success .beacon-core) {
  background: radial-gradient(circle at 35% 30%, #fff 0 8%, #50ffc1 9% 28%, #00b876 72%);
  box-shadow: 0 0 18px rgba(38, 229, 154, 0.9);
}
:deep(.beacon-success .beacon-halo) { background: rgba(38, 229, 154, 0.74); }

:deep(.beacon-info) { color: #2aa7ff; }
:deep(.beacon-info .beacon-core) {
  background: radial-gradient(circle at 35% 30%, #fff 0 8%, #62c9ff 9% 28%, #137bff 72%);
  box-shadow: 0 0 18px rgba(42, 167, 255, 0.9);
}
:deep(.beacon-info .beacon-halo) { background: rgba(42, 167, 255, 0.74); }

.event-stream {
  height: 168px;
  background: linear-gradient(135deg, rgba(13, 40, 68, 0.92) 0%, rgba(8, 22, 39, 0.94) 100%);
  border: 1px solid rgba(80, 183, 255, 0.2);
  border-radius: 8px;
  padding: 12px;
  overflow: hidden;
}

.stream-title {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  color: #dff7ff;
  font-weight: bold;
  margin-bottom: 8px;
}

.stream-title em {
  color: #68bce8;
  font-size: 10px;
  font-style: normal;
  letter-spacing: 1.4px;
}

.stream-list {
  height: calc(100% - 24px);
  overflow-y: auto;
}

.stream-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  font-size: 12px;
  border-bottom: 1px solid rgba(80, 183, 255, 0.08);
}

.stream-time {
  color: #a0cfff;
  min-width: 40px;
}

.stream-text {
  color: #e0e6ed;
  flex: 1;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}

.stat-item {
  text-align: center;
  padding: 10px 8px;
  background: linear-gradient(180deg, rgba(10, 36, 62, 0.92), rgba(7, 24, 43, 0.92));
  border: 1px solid rgba(80, 183, 255, 0.16);
  border-radius: 6px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #66ddff;
}

.stat-value.compact {
  font-size: 19px;
  line-height: 1.25;
  white-space: nowrap;
}

.stat-value.danger { color: #f56c6c; }
.stat-value.warning { color: #e6a23c; }
.stat-value.success { color: #67c23a; }
.stat-value.info { color: #409eff; }

.stat-label {
  font-size: 12px;
  color: #a0cfff;
  margin-top: 6px;
}

.chart-container {
  height: 154px;
  min-height: 154px;
}

.insight-card {
  min-height: 286px;
  flex: 0 0 286px;
}

.insight-card .card-title {
  margin-bottom: 14px;
}

.disaster-insight .chart-container {
  height: 128px;
  min-height: 128px;
}

.rescue-insight .chart-container {
  height: 128px;
  min-height: 128px;
}

.weather-card {
  flex: 0 0 176px;
  min-height: 176px;
}

.weather-card .card-title {
  margin-bottom: 10px;
}

.ai-card {
  flex: 0 0 316px;
  min-height: 316px;
}

.material-card {
  flex: 0 0 286px;
  min-height: 286px;
}

.material-card .chart-container {
  height: 120px;
  min-height: 120px;
}

.transfer-card {
  flex: 0 0 190px;
  min-height: 190px;
}

.transfer-card .stat-grid {
  grid-template-columns: repeat(2, 1fr);
  margin-bottom: 14px;
}

.weather-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
  max-height: 112px;
  overflow-y: auto;
}

.weather-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 30px;
  padding: 6px 8px;
  background: rgba(9, 30, 52, 0.78);
  border: 1px solid rgba(80, 183, 255, 0.1);
  border-radius: 4px;
}

.region {
  min-width: 50px;
  color: #e0e6ed;
}

.detail {
  color: #a0cfff;
  font-size: 12px;
}

.decision-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.decision-section {
  padding: 7px 10px;
  background: rgba(9, 30, 52, 0.78);
  border-radius: 4px;
  border-left: 3px solid #4fd7ff;
}

.section-label {
  color: #73dcff;
  font-weight: bold;
  font-size: 12px;
  margin-bottom: 4px;
}

.decision-section p {
  color: #e0e6ed;
  font-size: 12px;
  line-height: 1.36;
  margin: 0;
}

.empty-tip {
  color: #a0cfff;
  text-align: center;
  padding: 20px;
}

.progress-label {
  text-align: center;
  color: #a0cfff;
  font-size: 12px;
  margin-top: 8px;
}
</style>
