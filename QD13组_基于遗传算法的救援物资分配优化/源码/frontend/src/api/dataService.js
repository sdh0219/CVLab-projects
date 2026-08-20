/**
 * 加载优化结果数据
 * 优先从 API 读取 output 缓存，回退到 public/data/results.json
 */

/** 展示顺序：河南洪涝基准案例 → 两组模拟数据 */
export const DATASET_ORDER = [
  'henan_disaster',
  'dataset_01_large_scale',
  'dataset_02_complex_scenario',
]

export async function fetchResults() {
  try {
    const response = await fetch('/api/results')
    if (response.ok) {
      const raw = await response.json()
      return normalizeResults(raw)
    }
  } catch {
    // API 未启动时回退静态文件
  }

  const response = await fetch('/data/results.json')
  if (!response.ok) {
    throw new Error(`无法加载数据: ${response.status}`)
  }
  const raw = await response.json()
  return normalizeResults(raw)
}

/**
 * 流式运行遗传算法，通过 SSE 推送终端日志
 * @param {{ datasetIds?: string[], onLog?: (msg: string) => void }} options
 */
export function runOptimization({ datasetIds, onLog } = {}) {
  return new Promise((resolve, reject) => {
    const controller = new AbortController()

    fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ datasetIds: datasetIds ?? null }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const err = await response.json().catch(() => ({}))
          throw new Error(err.error || `运行失败: ${response.status}`)
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const parts = buffer.split('\n\n')
          buffer = parts.pop() || ''

          for (const part of parts) {
            const line = part.trim()
            if (!line.startsWith('data:')) continue
            const payload = JSON.parse(line.slice(5).trim())

            if (payload.type === 'log') {
              onLog?.(payload.message)
            } else if (payload.type === 'done') {
              resolve(payload)
              return
            } else if (payload.type === 'error') {
              throw new Error(payload.message)
            }
          }
        }
        resolve({})
      })
      .catch(reject)

    return () => controller.abort()
  })
}

export async function checkApiHealth() {
  try {
    const res = await fetch('/api/health')
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

function sortDatasets(datasets) {
  return [...datasets].sort((a, b) => {
    const ia = DATASET_ORDER.indexOf(a.id)
    const ib = DATASET_ORDER.indexOf(b.id)
    return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib)
  })
}

/** 统一为含 datasets 列表的结构，兼容单数据集旧格式 */
export function normalizeResults(raw) {
  if (raw.datasets?.length) {
    return { ...raw, datasets: sortDatasets(raw.datasets) }
  }
  const { generatedAt, datasets, ...single } = raw
  return {
    generatedAt: raw.generatedAt,
    datasets: [
      {
        id: 'default',
        name: raw.summary?.scenario || '默认数据集',
        ...single,
        generatedAt: raw.generatedAt,
      },
    ],
  }
}

export function getDatasetById(payload, id) {
  return payload.datasets.find((d) => d.id === id) || payload.datasets[0]
}

/** 从旧版 JSON 结构推断 inputData（兼容未重新导出的数据） */
export function buildInputDataFallback(dataset) {
  if (dataset.inputData) return dataset.inputData

  const materialNames = dataset.materialNames || dataset.summary?.materialNames || []
  const pointNames = dataset.pointNames || []
  const warehouseNames = dataset.warehouseNames || []

  return {
    materialNames,
    disasterPoints: pointNames.map((name) => ({
      name,
      population: 0,
      urgency: 1,
      demand: materialNames.map(() => 0),
    })),
    warehouses: warehouseNames.map((name) => ({
      name,
      vehicles: 0,
      vehicleCapacity: 0,
      maxTransport: 0,
      inventory: materialNames.map(() => 0),
    })),
    totals: {
      disasterPointsCount: dataset.summary?.disasterPointsCount ?? pointNames.length,
      warehousesCount: dataset.summary?.warehousesCount ?? warehouseNames.length,
      materialsCount: dataset.summary?.materialsCount ?? materialNames.length,
      population: dataset.summary?.totalPopulation ?? 0,
      demand: dataset.summary?.totalDemand ?? 0,
      inventory: dataset.summary?.totalInventory ?? 0,
    },
  }
}

export function formatNumber(num) {
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + ' 万'
  }
  return num.toLocaleString('zh-CN')
}

export function formatPercent(value, digits = 2) {
  return `${Number(value).toFixed(digits)}%`
}

const EMPTY_PLAN = { routeCount: 0, totalShipped: 0, routes: [], warehouseSummary: [] }

/** 从数据集构建运输方案（优先使用导出字段，否则从矩阵近似） */
export function getTransportPlan(dataset, variant = 'optimized') {
  const key = variant === 'initial' ? 'initialTransportPlan' : 'optimizedTransportPlan'
  if (dataset[key]?.routes?.length) return dataset[key]

  const matrixKey = variant === 'initial' ? 'initialAllocationMatrix' : 'allocationMatrix'
  const matrix = dataset[matrixKey]
  const input = buildInputDataFallback(dataset)
  if (!matrix?.length || !input.demandMatrix?.length) return EMPTY_PLAN

  return buildTransportPlanFromMatrix(
    matrix,
    input.demandMatrix,
    dataset.warehouseNames || [],
    dataset.pointNames || [],
    dataset.materialNames || input.materialNames || [],
    input.transportNetwork,
    input.warehouses || [],
  )
}

function roadConditionLabel(value) {
  if (value >= 0.85) return '通畅'
  if (value >= 0.6) return '一般'
  return '受阻'
}

/** 前端近似构建运输方案（无三维明细时按需求比例拆分物资） */
export function buildTransportPlanFromMatrix(
  matrix,
  demandMatrix,
  warehouseNames,
  pointNames,
  materialNames,
  transportNetwork,
  warehouseMeta,
) {
  const routes = []
  const whSummaryMap = {}

  warehouseNames.forEach((name, wi) => {
    const meta = warehouseMeta[wi] || {}
    whSummaryMap[wi] = {
      name,
      vehicles: meta.vehicles || 0,
      vehicleCapacity: meta.vehicleCapacity || 100,
      maxTransport: meta.maxTransport || 0,
      vehiclesUsed: 0,
      utilization: 0,
      totalShipped: 0,
      destinationCount: 0,
    }
  })

  matrix.forEach((row, wi) => {
    let destCount = 0
    row.forEach((total, pi) => {
      if (total <= 0.5) return
      destCount++

      const demand = demandMatrix[pi] || []
      const demandSum = demand.reduce((s, v) => s + Number(v), 0)
      const materials = materialNames.map((name, mi) => ({
        name,
        amount: demandSum > 0
          ? Math.round(total * Number(demand[mi] || 0) / demandSum)
          : Math.round(total / materialNames.length),
      })).filter((m) => m.amount > 0)

      const dist = transportNetwork?.distanceMatrix?.[wi]?.[pi] ?? 0
      const road = transportNetwork?.roadConditions?.[wi]?.[pi] ?? 1
      const time = transportNetwork?.transportTime?.[wi]?.[pi] ?? 0
      const cap = whSummaryMap[wi].vehicleCapacity || 100

      routes.push({
        warehouseIndex: wi,
        warehouseName: warehouseNames[wi],
        pointIndex: pi,
        pointName: pointNames[pi],
        materials,
        totalAmount: Math.round(total),
        distance: dist,
        roadCondition: road,
        roadLabel: roadConditionLabel(road),
        transportTime: time,
        transportCost: Math.round(total * dist / (road + 1e-10)),
        estimatedTrips: Math.ceil(total / cap),
      })

      whSummaryMap[wi].totalShipped += Math.round(total)
    })
    whSummaryMap[wi].destinationCount = destCount
  })

  Object.values(whSummaryMap).forEach((wh) => {
    if (wh.vehicleCapacity > 0) {
      wh.vehiclesUsed = Math.min(wh.vehicles, Math.ceil(wh.totalShipped / wh.vehicleCapacity))
      wh.utilization = wh.vehicles > 0 ? +(wh.vehiclesUsed / wh.vehicles).toFixed(2) : 0
    }
  })

  routes.sort((a, b) => b.totalAmount - a.totalAmount)

  return {
    routeCount: routes.length,
    totalShipped: routes.reduce((s, r) => s + r.totalAmount, 0),
    routes,
    warehouseSummary: Object.values(whSummaryMap),
  }
}
