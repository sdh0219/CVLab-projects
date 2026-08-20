<template>
  <div class="page-container">
    <div class="page-header">
      <h2>AI 辅助决策</h2>
    </div>

    <el-row :gutter="16" class="module-main-row">
      <!-- 左侧：自然语言输入 -->
      <el-col :span="10">
        <el-card class="dashboard-card decision-input-card">
          <template #header>
            <el-icon><Cpu /></el-icon>
            自然语言灾情输入
          </template>
          
          <div class="input-section">
            <el-form :model="formData" label-position="top">
              <el-form-item label="灾情描述">
                <el-input
                  v-model="formData.natural_language_input"
                  type="textarea"
                  :rows="6"
                  placeholder="请输入灾情描述，例如：&#10;红色暴雨预警，我市发生特大洪涝灾害。&#10;受灾人口约5000人，已有3人遇难，10人受伤。&#10;多条道路中断，5座桥梁受损。&#10;预计受灾面积50平方公里。&#10;当前有3家医院可用，需要紧急救援。"
                />
              </el-form-item>
              
              <el-form-item label="关联灾情事件（可选）">
                <el-select v-model="formData.disaster_event_id" style="width: 100%" clearable placeholder="选择关联事件">
                  <el-option
                    v-for="event in disasterEvents"
                    :key="event.id"
                    :label="event.event_name"
                    :value="event.id"
                  />
                </el-select>
              </el-form-item>
              
              <el-form-item>
                <el-button type="primary" @click="generateDecision" :loading="loading" size="large">
                  <el-icon><Cpu /></el-icon>
                  生成AI决策
                </el-button>
                <el-button @click="resetForm" size="large">重置</el-button>
              </el-form-item>
            </el-form>
          </div>

          <div class="workflow-section">
            <button 
              class="execute-btn"
              @click="generateDecision" 
              :disabled="loading"
            >
              <span v-if="loading">执行中...</span>
              <template v-else>
                <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
                执行工作流
              </template>
            </button>
            <div class="workflow-steps">
              <el-steps direction="vertical" :active="currentStep" finish-status="success">
                <el-step title="自然语言灾情输入" description="接收灾情描述" />
                <el-step title="AI信息抽取" description="提取结构化信息" />
                <el-step title="风险评估" description="评估风险等级" />
                <el-step title="案例匹配(RAG)" description="匹配历史案例" />
                <el-step title="资源需求预测" description="预测资源需求" />
                <el-step title="生成处置方案" description="生成处置方案" />
                <el-step title="生成指挥命令" description="生成指挥命令" />
              </el-steps>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：决策结果展示 -->
      <el-col :span="14">
        <el-card class="dashboard-card decision-output-card" v-if="decisionResult">
          <template #header>
            <el-icon><Document /></el-icon>
            AI决策结果
          </template>
          
          <el-tabs v-model="activeTab" type="border-card">
            <!-- 信息抽取 -->
            <el-tab-pane label="信息抽取" name="extracted">
              <div class="result-section">
                <h4><el-icon><Search /></el-icon> 结构化灾情信息</h4>
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="灾害类型">{{ translateDisasterType(decisionResult.extracted_info?.disaster_type) }}</el-descriptions-item>
                  <el-descriptions-item label="预警等级">{{ getWarningLevelText(decisionResult.extracted_info?.warning_level) }}</el-descriptions-item>
                  <el-descriptions-item label="受灾人口">{{ decisionResult.extracted_info?.affected_population || '未知' }}</el-descriptions-item>
                  <el-descriptions-item label="伤亡人数">{{ decisionResult.extracted_info?.casualties || '未知' }}</el-descriptions-item>
                  <el-descriptions-item label="受灾面积">{{ decisionResult.extracted_info?.affected_area ? decisionResult.extracted_info?.affected_area + '平方公里' : '未知' }}</el-descriptions-item>
                  <el-descriptions-item label="发生地点">{{ decisionResult.extracted_info?.location || '未知' }}</el-descriptions-item>
                </el-descriptions>
                <div v-if="decisionResult.extracted_info?.damaged_infrastructure" class="detail-section">
                  <h5>受损基础设施</h5>
                  <el-tag v-for="item in decisionResult.extracted_info.damaged_infrastructure" :key="item" class="tag-item">{{ item }}</el-tag>
                </div>
              </div>
            </el-tab-pane>

            <!-- 风险评估 -->
            <el-tab-pane label="风险评估" name="risk">
              <div class="result-section">
                <h4><el-icon><Warning /></el-icon> 风险评估结果</h4>
                <el-row :gutter="16">
                  <el-col :span="8">
                    <div class="risk-level">
                      <div class="risk-label">风险等级</div>
                      <div class="risk-value" :class="'risk-' + decisionResult.risk_assessment?.risk_level">
                        {{ decisionResult.risk_assessment?.risk_level || '未知' }}级
                      </div>
                    </div>
                  </el-col>
                  <el-col :span="8">
                    <div class="risk-level">
                      <div class="risk-label">风险评分</div>
                      <div class="risk-value score">{{ decisionResult.risk_assessment?.risk_score || 0 }}</div>
                    </div>
                  </el-col>
                  <el-col :span="8">
                    <div class="risk-level">
                      <div class="risk-label">转移紧迫性</div>
                      <div class="risk-value" :class="'urgency-' + decisionResult.risk_assessment?.evacuation_urgency">
                        {{ getUrgencyText(decisionResult.risk_assessment?.evacuation_urgency) }}
                      </div>
                    </div>
                  </el-col>
                </el-row>
                <div class="detail-section">
                  <h5>主要风险点</h5>
                  <el-tag v-for="item in decisionResult.risk_assessment?.primary_risks" :key="item" type="danger" class="tag-item">{{ item }}</el-tag>
                </div>
                <div class="detail-section">
                  <h5>次生灾害风险</h5>
                  <el-tag v-for="item in decisionResult.risk_assessment?.secondary_risks" :key="item" type="warning" class="tag-item">{{ item }}</el-tag>
                </div>
                <div class="detail-section">
                  <h5>评估总结</h5>
                  <p>{{ decisionResult.risk_assessment?.assessment_summary }}</p>
                </div>
              </div>
            </el-tab-pane>

            <!-- 案例匹配 -->
            <el-tab-pane label="案例匹配" name="cases">
              <div class="result-section">
                <h4><el-icon><Files /></el-icon> 相似历史案例</h4>
                <el-card v-for="caseItem in decisionResult.matched_cases" :key="caseItem.case_id" class="case-card" shadow="hover">
                  <div class="case-header">
                    <h5>{{ caseItem.case_name }}</h5>
                    <el-tag type="success">相似度: {{ caseItem.similarity_score }}%</el-tag>
                  </div>
                  <div class="case-content">
                    <div class="case-section">
                      <h6>关键措施</h6>
                      <el-tag v-for="measure in caseItem.key_measures" :key="measure" class="tag-item">{{ measure }}</el-tag>
                    </div>
                    <div class="case-section">
                      <h6>经验教训</h6>
                      <el-tag v-for="lesson in caseItem.lessons_learned" :key="lesson" type="info" class="tag-item">{{ lesson }}</el-tag>
                    </div>
                  </div>
                </el-card>
              </div>
            </el-tab-pane>

            <!-- 资源预测 -->
            <el-tab-pane label="资源预测" name="resources">
              <div class="result-section">
                <h4><el-icon><UserFilled /></el-icon> 资源需求预测</h4>
                
                <h5>救援队伍</h5>
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="消防员">{{ decisionResult.resource_prediction?.rescue_teams?.firefighters || 0 }}人</el-descriptions-item>
                  <el-descriptions-item label="医疗队">{{ decisionResult.resource_prediction?.rescue_teams?.medical_teams || 0 }}支</el-descriptions-item>
                  <el-descriptions-item label="搜救队">{{ decisionResult.resource_prediction?.rescue_teams?.search_rescue || 0 }}支</el-descriptions-item>
                  <el-descriptions-item label="工程人员">{{ decisionResult.resource_prediction?.rescue_teams?.engineers || 0 }}人</el-descriptions-item>
                </el-descriptions>

                <h5>应急物资</h5>
                <el-descriptions :column="3" border>
                  <el-descriptions-item label="帐篷">{{ decisionResult.resource_prediction?.materials?.tents || 0 }}顶</el-descriptions-item>
                  <el-descriptions-item label="食品">{{ decisionResult.resource_prediction?.materials?.food_rations || 0 }}份</el-descriptions-item>
                  <el-descriptions-item label="饮用水">{{ decisionResult.resource_prediction?.materials?.water_bottles || 0 }}瓶</el-descriptions-item>
                  <el-descriptions-item label="医疗物资">{{ decisionResult.resource_prediction?.materials?.medical_supplies || 0 }}套</el-descriptions-item>
                  <el-descriptions-item label="发电机">{{ decisionResult.resource_prediction?.materials?.generators || 0 }}台</el-descriptions-item>
                  <el-descriptions-item label="毛毯">{{ decisionResult.resource_prediction?.materials?.blankets || 0 }}条</el-descriptions-item>
                </el-descriptions>

                <h5>装备设备</h5>
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="无人机">{{ decisionResult.resource_prediction?.equipment?.drones || 0 }}架</el-descriptions-item>
                  <el-descriptions-item label="车辆">{{ decisionResult.resource_prediction?.equipment?.vehicles || 0 }}辆</el-descriptions-item>
                  <el-descriptions-item label="冲锋舟">{{ decisionResult.resource_prediction?.equipment?.boats || 0 }}艘</el-descriptions-item>
                  <el-descriptions-item label="通信设备">{{ decisionResult.resource_prediction?.equipment?.communication_devices || 0 }}套</el-descriptions-item>
                </el-descriptions>

                <div class="detail-section">
                  <h5>预测总结</h5>
                  <p>{{ decisionResult.resource_prediction?.prediction_summary }}</p>
                </div>
              </div>
            </el-tab-pane>

            <!-- 处置方案 -->
            <el-tab-pane label="处置方案" name="plan">
              <div class="result-section">
                <h4><el-icon><Document /></el-icon> 应急处置方案</h4>
                <div class="plan-content" v-html="formatPlan(decisionResult.response_plan)"></div>
              </div>
            </el-tab-pane>

            <!-- 指挥命令 -->
            <el-tab-pane label="指挥命令" name="commands">
              <div class="result-section">
                <h4><el-icon><Bell /></el-icon> 指挥命令清单</h4>
                <el-table :data="decisionResult.command_orders" stripe>
                  <el-table-column prop="command_id" label="命令编号" width="120" />
                  <el-table-column prop="command_type" label="类型" width="120">
                    <template #default="{ row }">
                      <el-tag :type="getCommandTypeColor(row.command_type)">{{ translateCommandType(row.command_type) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="target_unit" label="执行单位" width="150" />
                  <el-table-column prop="command_content" label="命令内容" show-overflow-tooltip />
                  <el-table-column prop="priority" label="优先级" width="100">
                    <template #default="{ row }">
                      <el-tag :type="row.priority === 'high' ? 'danger' : row.priority === 'medium' ? 'warning' : 'info'" size="small">
                        {{ row.priority === 'high' ? '高' : row.priority === 'medium' ? '中' : '低' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="deadline" label="时限" width="100" />
                </el-table>
              </div>
            </el-tab-pane>
          </el-tabs>

          <div class="result-actions">
            <el-button type="success" @click="confirmDecision(decisionResult.id)">确认采纳</el-button>
            <el-button type="danger" @click="rejectDecision(decisionResult.id)">退回</el-button>
          </div>
        </el-card>

        <el-card class="dashboard-card empty-card" v-else>
          <el-empty description="请输入灾情描述并生成AI决策" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 历史决策记录 -->
    <el-card class="dashboard-card history-card">
      <template #header>历史决策记录</template>
      <el-table :data="decisionHistory" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="灾情输入" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.input_data?.substring(0, 50) || '' }}...
          </template>
        </el-table-column>
        <el-table-column label="风险等级" width="100">
          <template #default="{ row }">
            <el-tag :type="row.risk_assessment?.risk_level === 'I' || row.risk_assessment?.risk_level === 'II' ? 'danger' : 'warning'" size="small">
              {{ row.risk_assessment?.risk_level || '未知' }}级
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="案例匹配" width="120">
          <template #default="{ row }">
            {{ row.matched_cases?.length || 0 }}个案例
          </template>
        </el-table-column>
        <el-table-column label="指挥命令" width="100">
          <template #default="{ row }">
            {{ row.command_orders?.length || 0 }}条命令
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'confirmed' ? 'success' : row.status === 'rejected' ? 'danger' : 'warning'" size="small">
              {{ row.status === 'confirmed' ? '已确认' : row.status === 'rejected' ? '已拒绝' : '待确认' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewDecision(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { createAIDecision, getAIDecisions, getDisasters, confirmAIDecision, rejectAIDecision } from '../api'

const loading = ref(false)
const decisionResult = ref(null)
const decisionHistory = ref([])
const disasterEvents = ref([])
const activeTab = ref('extracted')
const currentStep = ref(0)

const formData = ref({
  natural_language_input: '',
  disaster_event_id: null
})

function translateDisasterType(type) {
  const map = {
    flood: '洪涝',
    earthquake: '地震',
    forest_fire: '森林火灾',
    extreme_weather: '极端天气'
  }
  return map[type] || type || '未知'
}

function getWarningLevelText(level) {
  const map = { red: '红色', orange: '橙色', yellow: '黄色', blue: '蓝色' }
  return map[level] || '未知'
}

function getUrgencyText(urgency) {
  const map = { high: '高', medium: '中', low: '低' }
  return map[urgency] || '未知'
}

function translateCommandType(type) {
  const map = {
    deployment: '部署',
    evacuation: '转移',
    allocation: '调拨',
    rescue: '救援',
    other: '其他'
  }
  return map[type] || type
}

function getCommandTypeColor(type) {
  const map = {
    deployment: 'danger',
    evacuation: 'warning',
    allocation: 'success',
    rescue: 'primary',
    other: 'info'
  }
  return map[type] || 'info'
}

function formatPlan(plan) {
  if (!plan) return ''
  return plan.replace(/\n/g, '<br>')
}

async function generateDecision() {
  if (!formData.value.natural_language_input.trim()) {
    ElMessage.warning('请输入灾情描述')
    return
  }

  loading.value = true
  currentStep.value = 0
  
  try {
    // 模拟工作流步骤动画
    const stepInterval = setInterval(() => {
      if (currentStep.value < 6) {
        currentStep.value++
      }
    }, 500)

    const result = await createAIDecision({
      natural_language_input: formData.value.natural_language_input,
      disaster_event_id: formData.value.disaster_event_id
    })

    clearInterval(stepInterval)
    currentStep.value = 7

    decisionResult.value = result.data
    ElMessage.success('AI决策生成成功')
    
    // 重新加载历史
    await loadHistory()
  } catch (e) {
    ElMessage.error('生成决策失败: ' + (e.response?.data?.detail || e.message))
    currentStep.value = 0
  } finally {
    loading.value = false
  }
}

function resetForm() {
  formData.value = {
    natural_language_input: '',
    disaster_event_id: null
  }
  decisionResult.value = null
  currentStep.value = 0
}

async function confirmDecision(id) {
  try {
    await confirmAIDecision(id)
    ElMessage.success('决策已采纳')
    decisionResult.value = null
    await loadHistory()
  } catch (e) {
    ElMessage.error('确认失败')
  }
}

async function rejectDecision(id) {
  try {
    await rejectAIDecision(id)
    ElMessage.success('决策已退回')
    decisionResult.value = null
    await loadHistory()
  } catch (e) {
    ElMessage.error('拒绝失败')
  }
}

async function viewDecision(row) {
  decisionResult.value = row
  activeTab.value = 'extracted'
  currentStep.value = 7
}

async function loadHistory() {
  try {
    const response = await getAIDecisions()
    decisionHistory.value = response.data
  } catch (e) {
    console.error('加载历史失败:', e)
  }
}

async function loadDisasterEvents() {
  try {
    const response = await getDisasters()
    disasterEvents.value = response.data
  } catch (e) {
    console.error('加载灾情事件失败:', e)
  }
}

onMounted(() => {
  loadHistory()
  loadDisasterEvents()
})
</script>

<style scoped>
.page-container { padding: 20px; }
.page-header { margin-bottom: 20px; }
.page-header h2 { color: #00d4ff; }
.dashboard-card { background: #0d2137; border: 1px solid #1a3a5c; }
.dashboard-card :deep(.el-card__header) { border-bottom: 1px solid #1a3a5c; color: #00d4ff; }

.module-main-row {
  margin-bottom: 20px;
}

.decision-input-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.decision-output-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 180px);
  padding: 0;
}

.decision-output-card :deep(.el-card__body) .el-tabs {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  margin: 0;
}

.decision-output-card :deep(.el-card__body) .el-tabs .el-tabs__content {
  flex: 1;
  overflow-y: auto;
}

.result-actions {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid #1a3a5c;
  background: #0d2137;
  flex-shrink: 0;
}

.input-section {
  padding: 10px;
}

.input-section :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

.input-section :deep(.el-form-item__content) {
  display: flex;
  gap: 12px;
}

.workflow-steps {
  padding: 16px;
  background: rgba(8, 26, 45, 0.72);
  border-radius: 8px;
}

.workflow-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #1a3a5c;
}

.step-title {
  color: #00d4ff;
  font-weight: bold;
  font-size: 16px;
}

.workflow-btn {
  min-width: 140px;
  --el-button-bg-color: #00d4ff !important;
  --el-button-border-color: #00d4ff !important;
  --el-button-text-color: #0d2137 !important;
  --el-button-hover-bg-color: #33e0ff !important;
  --el-button-hover-border-color: #33e0ff !important;
  --el-button-hover-text-color: #0d2137 !important;
  font-weight: bold;
}

:deep(.workflow-btn) {
  background: #00d4ff !important;
  border-color: #00d4ff !important;
  color: #0d2137 !important;
}

:deep(.workflow-btn span) {
  color: #0d2137 !important;
}

:deep(.workflow-btn .el-icon) {
  color: #0d2137 !important;
}

.result-section {
  padding: 10px;
}

.result-section h4 {
  color: #00d4ff;
  margin: 0 0 12px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-section h5 {
  color: #66ddff;
  margin: 12px 0 8px 0;
}

.detail-section {
  margin-top: 12px;
}

.tag-item {
  margin: 4px;
}

.risk-level {
  text-align: center;
  padding: 16px;
  background: rgba(8, 26, 45, 0.72);
  border-radius: 8px;
}

.risk-label {
  color: #8fb7d8;
  font-size: 14px;
  margin-bottom: 8px;
}

.risk-value {
  font-size: 28px;
  font-weight: bold;
}

.risk-I, .risk-II {
  color: #f56c6c;
}

.risk-III {
  color: #e6a23c;
}

.risk-IV {
  color: #67c23a;
}

.score {
  color: #00d4ff;
}

.urgency-high {
  color: #f56c6c;
}

.urgency-medium {
  color: #e6a23c;
}

.urgency-low {
  color: #67c23a;
}

.case-card {
  margin-bottom: 12px;
  background: rgba(8, 26, 45, 0.72);
  border: 1px solid #1a3a5c;
}

.case-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.case-header h5 {
  color: #00d4ff;
  margin: 0;
}

.case-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.case-section h6 {
  color: #66ddff;
  margin: 0 0 8px 0;
}

.plan-content {
  color: #e0e6ed;
  line-height: 1.6;
  white-space: pre-wrap;
}

.result-actions {
  display: flex;
  gap: 12px;
  padding-top: 16px;
  margin-top: 16px;
  border-top: 1px solid #1a3a5c;
}

.empty-card {
  min-height: 600px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.history-card {
  margin-top: 20px;
}

:deep(.el-tabs--border-card) {
  background: rgba(8, 26, 45, 0.72);
  border-color: #1a3a5c;
}

:deep(.el-tabs__header) {
  background: rgba(8, 26, 45, 0.72);
}

:deep(.el-tabs__item) {
  color: #a0cfff;
}

:deep(.el-tabs__item.is-active) {
  color: #00d4ff;
}

:deep(.el-descriptions__label) {
  color: #66ddff;
}

:deep(.el-descriptions__content) {
  color: #e0e6ed;
}

:deep(.el-table) {
  background: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(8, 26, 45, 0.72);
  --el-table-row-hover-bg-color: rgba(0, 212, 255, 0.1);
}

:deep(.el-table th) {
  color: #00d4ff;
}

:deep(.el-table td) {
  color: #e0e6ed;
}
</style>
