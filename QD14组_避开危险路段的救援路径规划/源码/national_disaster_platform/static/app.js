let scenarios = [];
let currentId = null;
let running = false;
let demoPlayedSteps = -1;
let currentStepIndex = -1;

const $ = (id) => document.getElementById(id);

function formatNumber(value) {
  const number = Number(value || 0);
  return number.toLocaleString("zh-CN");
}

function valueOrNone(value) {
  if (value === undefined || value === null || value === "") return "无";
  return value;
}

async function loadScenarios() {
  const response = await fetch("/api/scenarios");
  scenarios = await response.json();
  renderMarkers();
  renderScenarioList();
  selectScenario(scenarios[0].id);
}

function renderMarkers() {
  const box = $("mapMarkers");
  box.innerHTML = "";
  scenarios.forEach((scene) => {
    const marker = document.createElement("button");
    marker.className = `map-marker ${scene.type}`;
    marker.style.left = `${scene.marker.x}%`;
    marker.style.top = `${scene.marker.y}%`;
    marker.title = scene.title;
    marker.innerHTML = `<span>${scene.province}</span>`;
    marker.addEventListener("click", () => selectScenario(scene.id));
    marker.dataset.id = scene.id;
    box.appendChild(marker);
  });
}

function renderScenarioList() {
  const list = $("scenarioList");
  list.innerHTML = "";
  scenarios.forEach((scene) => {
    const card = document.createElement("div");
    card.className = "scenario-card";
    card.dataset.id = scene.id;
    card.innerHTML = `<strong>${scene.title}</strong><span>${scene.event}｜${scene.start} → ${scene.target}</span>`;
    card.addEventListener("click", () => selectScenario(scene.id));
    list.appendChild(card);
  });
}

async function selectScenario(id) {
  currentId = id;
  demoPlayedSteps = -1;
  currentStepIndex = -1;
  const scene = scenarios.find((item) => item.id === id);
  updateActiveState(id);
  renderScene(scene);
}

function updateActiveState(id) {
  document.querySelectorAll(".scenario-card").forEach((item) => {
    item.classList.toggle("active", item.dataset.id === id);
  });
  document.querySelectorAll(".map-marker").forEach((item) => {
    item.classList.toggle("active", item.dataset.id === id);
  });
}

function renderScene(scene) {
  $("typeBadge").textContent = scene.type_label;
  $("sceneTitle").textContent = scene.title;
  $("sceneSummary").textContent = scene.summary;
  $("sceneDate").textContent = scene.date;
  $("scenePlace").textContent = `${scene.province} · ${scene.city}`;
  $("routeImage").src = `${scene.routeImage}&t=${Date.now()}`;

  $("nodeCount").textContent = formatNumber(scene.stats.nodes);
  $("edgeCount").textContent = formatNumber(scene.stats.edges);
  $("riskEdgeCount").textContent = formatNumber(scene.stats.mappedDangerEdges);
  $("trafficEdgeCount").textContent = formatNumber(scene.stats.trafficMappedEdges);

  const distance = scene.result.distance || {};
  const safe = scene.result.safe || {};
  $("distanceKm").textContent = `${valueOrNone(distance.total_distance)} km`;
  $("distanceDanger").textContent = valueOrNone(distance.dangerous_edge_count);
  $("distanceTypes").textContent = valueOrNone(distance.danger_types);
  $("safeKm").textContent = `${valueOrNone(safe.total_distance)} km`;
  $("safeCost").textContent = valueOrNone(safe.total_cost);
  $("safeTypes").textContent = valueOrNone(safe.danger_types);

  renderPipeline(scene.pipeline);
  updateStageOverlay("最终结果", "点击下方步骤可查看每一层叠加效果");
  $("logBox").textContent = [
    `当前场景：${scene.title}`,
    `历史灾害：${scene.event}`,
    `重点风险：${scene.hazard}`,
    `数据目录：${scene.dataDir}`,
  ].join("\n");
}

// ---------- 流水线步骤 ----------

const STEP_LABELS = [
  "选择历史灾害事件和救援起终点",
  "抓取/加载该区域真实 OSM 道路网络",
  "叠加历史灾害影响区并识别危险路段",
  "叠加高德交通态势中的拥堵路段",
  "运行 Dijkstra：距离权重得到普通最短路径",
  "运行 Dijkstra：安全权重得到安全救援路径",
  "输出路径对比表和可视化路线图",
];

function renderPipeline(steps, activeIndex = -1) {
  const box = $("pipeline");
  box.innerHTML = "";
  const scene = scenarios.find((item) => item.id === currentId);
  const stepPaths = scene ? (scene.pipelineSteps || []) : [];

  steps.forEach((step, index) => {
    const item = document.createElement("div");
    item.className = "pipe-step";
    if (index === activeIndex) {
      item.classList.add("active");
    }
    if (index <= demoPlayedSteps && demoPlayedSteps >= 0) {
      item.classList.add("played");
    }
    item.textContent = `${index + 1}. ${step}`;

    if (stepPaths[index]) {
      item.classList.add("clickable");
      item.title = `点击查看：${STEP_LABELS[index] || step}`;
      item.addEventListener("click", () => {
        if (running) return;
        jumpToStep(index, scene, stepPaths);
      });
    }

    box.appendChild(item);
  });
}

function jumpToStep(index, scene, stepPaths, options = {}) {
  currentStepIndex = index;
  const stepLabel = STEP_LABELS[index] || scene.pipeline[index] || `步骤 ${index + 1}`;
  updateStageOverlay(`第 ${index + 1} 步`, stepLabel);

  const imgPath = stepPaths[index];
  if (imgPath) {
    $("routeImage").src = `/artifact?path=${imgPath}&t=${Date.now()}`;
  } else {
    $("routeImage").src = `${scene.routeImage}&t=${Date.now()}`;
  }

  document.querySelectorAll(".pipe-step").forEach((el, i) => {
    el.classList.toggle("active", i === index);
  });

  if (!options.preserveLog) {
    $("logBox").textContent = [
      `[${new Date().toLocaleTimeString()}] 第 ${index + 1} 步：${stepLabel}`,
      `（手动选择查看此步骤）`,
    ].join("\n");
  }
}

function updateStageOverlay(title, description) {
  const overlay = $("stageOverlay");
  if (!overlay) return;
  overlay.querySelector("strong").textContent = title;
  overlay.querySelector("span").textContent = description;
}

// ---------- 快速演示模式 ----------

async function runDemo() {
  if (running || !currentId) return;
  running = true;
  demoPlayedSteps = -1;
  currentStepIndex = 0;

  const scene = scenarios.find((item) => item.id === currentId);
  const stepPaths = scene.pipelineSteps || [];
  const totalSteps = stepPaths.length || scene.pipeline.length;

  $("demoBtn").disabled = true;
  $("runPipelineBtn").disabled = true;

  const logs = [];
  logs.push("[快速演示] 播放已由真实流水线生成的阶段结果图，适合录制演示视频。");

  for (let i = 0; i < totalSteps; i += 1) {
    currentStepIndex = i;
    const stepLabel = STEP_LABELS[i] || scene.pipeline[i] || `步骤 ${i + 1}`;

    demoPlayedSteps = i;
    renderPipeline(scene.pipeline, i);

    updateStageOverlay(`第 ${i + 1} 步`, stepLabel);

    logs.push(`[${new Date().toLocaleTimeString()}] 第 ${i + 1} 步：${stepLabel}`);
    $("logBox").textContent = logs.join("\n");

    if (stepPaths[i]) {
      $("routeImage").src = `/artifact?path=${stepPaths[i]}&t=${Date.now()}`;
    } else {
      $("routeImage").src = `${scene.routeImage}&t=${Date.now()}`;
    }

    await new Promise((resolve) => setTimeout(resolve, 2500));
  }

  demoPlayedSteps = totalSteps - 1;
  currentStepIndex = totalSteps - 1;
  const lastLabel = STEP_LABELS[totalSteps - 1] || scene.pipeline[totalSteps - 1] || `步骤 ${totalSteps}`;
  updateStageOverlay(`第 ${totalSteps} 步（完成）`, lastLabel);

  logs.push("[完成] 快速演示已结束，当前显示最终结果图。");
  $("logBox").textContent = logs.join("\n");

  $("demoBtn").disabled = false;
  $("runPipelineBtn").disabled = false;
  running = false;
}

// ---------- 真实运行流水线模式 ----------

async function runRealPipeline() {
  if (running || !currentId) return;
  running = true;
  $("demoBtn").disabled = true;
  $("runPipelineBtn").disabled = true;

  try {
    $("logBox").textContent = "[真实运行] 开始执行本地流水线，调用真实脚本...";
    updateStageOverlay("真实运行中", "正在执行 Dijkstra 计算和可视化生成...");

    const response = await fetch(`/api/run-pipeline/${currentId}`, { method: "POST" });
    let payload;
    try {
      payload = await response.json();
    } catch (parseErr) {
      $("logBox").textContent = `[错误] 后端返回非 JSON 数据：${parseErr.message || parseErr}`;
      return;
    }

    if (!payload.ok) {
      $("logBox").textContent = [
        `[错误] 真实运行失败，用时 ${payload.elapsed || 0} 秒`,
        "---",
        ...(payload.logs || []),
      ].join("\n");
      return;
    }

    // 刷新当前场景数据
    const refreshed = await fetch(`/api/scenarios/${currentId}`).then((res) => res.json());
    scenarios = scenarios.map((item) => (item.id === currentId ? refreshed : item));
    demoPlayedSteps = 6;
    renderPipeline(refreshed.pipeline, 6);

    $("logBox").textContent = [
      `[真实运行] 流水线执行完成，用时 ${payload.elapsed || 0} 秒`,
      `[真实运行] 已刷新步骤图和最终结果图`,
      "---",
      ...(payload.logs || []),
    ].join("\n");

    // 直接显示第 7 步图片，但不覆盖日志
    const stepPaths = refreshed.pipelineSteps || [];
    if (stepPaths[6]) {
      jumpToStep(6, refreshed, stepPaths, { preserveLog: true });
    } else {
      renderScene(refreshed);
    }
  } catch (err) {
    $("logBox").textContent = [
      `[错误] 真实运行异常：${err.message || err}`,
      "---",
      "请检查后端是否正在运行，或稍后重试。",
    ].join("\n");
  } finally {
    $("demoBtn").disabled = false;
    $("runPipelineBtn").disabled = false;
    running = false;
  }
}

$("demoBtn").addEventListener("click", runDemo);
$("runPipelineBtn").addEventListener("click", runRealPipeline);

loadScenarios().catch((error) => {
  $("logBox").textContent = `平台加载失败：${error}`;
});
