import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 10000
})

// 灾情
export const getDisasters = () => api.get('/api/disasters/')
export const getDisasterStats = () => api.get('/api/disasters/statistics')

// 救援
export const getRescueTeams = (params) => api.get('/api/rescue/teams', { params })
export const getNearestRescue = (params) => api.get('/api/rescue/nearest', { params })
export const getRescueStats = () => api.get('/api/rescue/statistics')

// 物资
export const getMaterials = () => api.get('/api/materials/')
export const getMaterialStats = () => api.get('/api/materials/statistics')
export const calculateDemand = (params) => api.post('/api/materials/calculate-demand', null, { params })

// 转移
export const getShelters = () => api.get('/api/evacuation/shelters')
export const getTransfers = () => api.get('/api/evacuation/transfers')
export const getEvacuationPlan = (params) => api.get('/api/evacuation/plan', { params })
export const getEvacuationStats = () => api.get('/api/evacuation/statistics')

// AI决策
export const createAIDecision = (data) => api.post('/api/ai/decision', data)
export const getAIDecisions = () => api.get('/api/ai/decisions')
export const confirmAIDecision = (id) => api.patch(`/api/ai/decisions/${id}/confirm`)
export const rejectAIDecision = (id) => api.patch(`/api/ai/decisions/${id}/reject`)

// 公共
export const getDashboard = () => api.get('/api/common/dashboard')
export const getWeather = () => api.get('/api/common/weather')
export const getRoads = () => api.get('/api/common/roads')
export const getPopulation = () => api.get('/api/common/population')
