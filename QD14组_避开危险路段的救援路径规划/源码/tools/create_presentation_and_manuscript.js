const fs = require("node:fs/promises");
const path = require("node:path");
const { Presentation, PresentationFile } = require("@oai/artifact-tool");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "outputs", "final_presentation");
const SCRATCH = path.join(process.env.TEMP || OUT_DIR, "codex-presentations", "project14-real-disaster");
const PREVIEW_DIR = path.join(SCRATCH, "preview");
const LAYOUT_DIR = path.join(SCRATCH, "layout");
const QA_DIR = path.join(SCRATCH, "qa");

const PPTX_PATH = path.join(OUT_DIR, "项目14_避开危险路段的救援路径规划_汇报PPT_真实历史灾害数据版.pptx");
const MANUSCRIPT_MD = path.join(OUT_DIR, "项目14_避开危险路段的救援路径规划_详细汇报手稿_真实历史灾害数据版.md");

const COLORS = {
  bg: "#F7FAFC",
  ink: "#102033",
  muted: "#5B677A",
  line: "#D9E2EC",
  navy: "#18213A",
  blue: "#1F5EFF",
  green: "#178A4A",
  teal: "#0E9384",
  red: "#D64545",
  orange: "#E58B25",
  paleBlue: "#EAF2FF",
  paleGreen: "#E8F6EE",
  paleRed: "#FDECEC",
  paleOrange: "#FFF2DF",
  white: "#FFFFFF",
};

const FONT = "Microsoft YaHei";

const slides = [
  {
    section: "项目14 | 模块3 应急响应",
    title: "避开危险路段的救援路径规划",
    kind: "cover",
    body: [
      "真实地图数据：高德 Web 服务路线数据",
      "真实历史灾害资料：地震与暴雨洪水案例",
      "核心方法：空间叠加识别危险路段 + Dijkstra 安全路径规划",
    ],
    note:
      "各位老师好，我们汇报的项目是避开危险路段的救援路径规划。这个项目对应模块3应急响应。新版项目的重点是使用真实地图数据和真实历史灾害资料。地图道路来自高德 Web 服务，灾害信息来自公开历史灾害记录。我们不是直接手动说某条路危险，而是把历史灾害影响区和真实道路做空间叠加，再用 Dijkstra 算法计算普通最短路径和安全路径。",
  },
  {
    section: "一、问题背景",
    title: "灾害救援不能只看最短距离",
    kind: "bullets",
    body: [
      "灾害后道路状态会变化，可能出现塌方、积水、拥堵和局部中断。",
      "普通导航偏向距离最短或时间最短，但救援车辆更重视安全性和通行可靠性。",
      "本项目把灾害影响转化为道路权重，让算法主动绕开高风险区域。",
      "核心结论：最短路径不一定是最适合救援的路径。",
    ],
    note:
      "灾害发生后，道路网络不再是平时的状态。比如暴雨会造成桥区积水，地震会造成建筑损坏或道路塌方，交通拥堵也会影响救援效率。如果救援车辆只按照普通导航走最近路线，可能会进入高风险路段。因此本项目把道路安全性也纳入路径规划。",
  },
  {
    section: "二、项目目标",
    title: "真实道路 + 历史灾害 + Dijkstra",
    kind: "cards",
    body: [
      ["真实道路", "调用高德 Web 服务，获取道路名称、距离、路线坐标和交通状态。"],
      ["历史灾害", "整理地震和洪水两个公开历史灾害案例，作为场景依据。"],
      ["空间映射", "将灾害影响区与道路边叠加，自动识别危险路段。"],
      ["路径规划", "只使用 Dijkstra，分别计算普通最短路径和安全路径。"],
    ],
    note:
      "项目目标可以概括成四点。第一，用真实道路数据，不再完全依赖模拟路网。第二，加入真实历史灾害资料。第三，用空间叠加方法判断哪些道路受到灾害影响。第四，只使用 Dijkstra 算法，分别用距离权重和安全权重计算两条路径。",
  },
  {
    section: "三、数据来源",
    title: "地图数据和灾害数据分开说明",
    kind: "split",
    body: {
      leftTitle: "真实地图数据",
      left: [
        "来源：高德 Web 服务路径规划 API",
        "字段：道路名称、距离、导航指令、路线坐标、交通状态",
        "用途：构建真实道路节点和道路边",
      ],
      rightTitle: "历史灾害数据",
      right: [
        "地震：1679 年三河-平谷地震公开历史资料",
        "洪水：2012 年北京 7·21 特大暴雨资料",
        "用途：构建灾害影响区并映射到道路",
      ],
    },
    note:
      "这里需要特别说明数据来源。高德提供的是道路层面的真实地图数据，包括道路距离、道路名称和路线坐标。历史灾害资料提供的是灾害事件的时间、类型、区域和影响说明。两类数据本身不是一个格式，所以我们用空间叠加把灾害影响区投到道路网络上。",
  },
  {
    section: "四、数据精度说明",
    title: "真实灾害数据不等于逐路段封闭表",
    kind: "statement",
    body: [
      "公开历史灾害资料通常能说明灾害发生时间、区域、强度和影响。",
      "但它很少直接给出每条道路是否塌方、积水或封闭。",
      "因此本项目采用：历史灾害事件 -> 影响区缓冲 -> 道路叠加 -> 危险路段。",
    ],
    note:
      "这一页是为了回应老师可能会问的数据精度问题。真实历史灾害资料并不一定精确到每条街道。我们的处理方式是：先确定真实灾害事件，再建立灾害影响区缓冲区，然后判断真实道路是否进入这个影响区。这样得到的危险路段是计算出来的，不是随便指定的。",
  },
  {
    section: "五、空间叠加方法",
    title: "灾害影响区如何变成危险路段",
    kind: "flow",
    body: ["历史灾害事件", "影响区缓冲", "高德道路边", "线段距离判断", "危险路段标记", "Dijkstra 计算"],
    note:
      "具体流程是这样的：首先读取历史灾害事件表，每条事件有经纬度和影响半径。然后把道路边看成由两个节点组成的线段。程序计算灾害影响中心到道路边线段的最短距离。如果这个距离小于影响半径，就说明道路进入灾害影响区，于是地震场景标记为塌方风险，洪水场景标记为积水风险。",
  },
  {
    section: "六、道路图模型",
    title: "把真实道路抽象成图结构",
    kind: "table",
    body: [
      ["节点", "高德路线坐标点、救援出发点、受灾终点"],
      ["边", "相邻节点之间的道路路段"],
      ["边属性", "距离、道路名称、危险类型、拥堵程度、通行状态"],
      ["输出", "nodes.csv、edges.csv、road_disaster_mapping.csv"],
    ],
    note:
      "算法不能直接处理地图图片，所以我们需要把道路抽象成图结构。节点是路线上的坐标点，边是两个节点之间的道路。每条边保存距离、拥堵程度和危险类型。这样 Dijkstra 就可以在图上搜索路线。",
  },
  {
    section: "七、权重设计",
    title: "安全路径的综合权重",
    kind: "formula",
    body: {
      formula: "safe_weight = distance × risk_factor × (1 + 0.6 × congestion)",
      bullets: [
        "普通最短路径：只使用 distance。",
        "安全路径：同时考虑距离、灾害风险和拥堵程度。",
        "风险系数越高，道路综合代价越大，算法越倾向绕行。",
        "塌方系数 4.0，积水系数 2.2，拥堵系数 1.4，正常道路 1.0。",
      ],
    },
    note:
      "普通最短路径只看道路距离。安全路径则使用综合权重，等于距离乘以风险系数，再乘以拥堵修正项。比如一段路本来距离不长，但如果处于积水或塌方影响区，它的综合代价会明显变大，算法就会优先选择其他路线。",
  },
  {
    section: "八、Dijkstra 算法",
    title: "只使用 Dijkstra 完成两种路径搜索",
    kind: "steps",
    body: [
      "起点代价设为 0，其他节点设为无穷大。",
      "每次选择当前累计代价最小的节点。",
      "检查相邻道路，如果新代价更低就更新。",
      "到达终点后回溯前驱节点，得到完整路径。",
      "分别用 distance 和 safe_weight 运行两次。",
    ],
    note:
      "Dijkstra 是一种经典的最短路径算法，适合边权重非负的图。本项目中道路距离和综合安全权重都是非负数，所以适合使用 Dijkstra，整个算法部分保持简单清晰。",
  },
  {
    section: "九、地震场景结果",
    title: "普通路径经过地震影响区，安全路径绕行",
    kind: "comparison",
    body: [
      ["普通最短路径", "19.973 km", "19.973", "collapse, congestion", "距离较短，但经过历史地震影响区。"],
      ["安全路径", "26.816 km", "32.209", "congestion", "距离增加，但绕开主要塌方风险。"],
    ],
    note:
      "地震场景中，普通最短路径距离是 19.973 公里，但是危险类型包含 collapse 和 congestion，说明它经过了历史地震影响区。安全路径距离为 26.816 公里，虽然更长，但危险类型只剩拥堵，说明它绕开了主要塌方风险。",
  },
  {
    section: "十、地震场景可视化",
    title: "红色区域表示历史地震影响区",
    kind: "map",
    body: "outputs/amap_earthquake/route_map_amap_static.png",
    note:
      "这一页展示地震场景的真实高德地图底图叠加图。红色半透明区域是历史地震影响区，蓝色粗线是普通最短路径，绿色粗线是安全路径。可以看到普通路径穿过影响区，而安全路径选择了绕行。",
  },
  {
    section: "十一、洪水场景结果",
    title: "普通路径经过积水风险区，安全路径绕行",
    kind: "comparison",
    body: [
      ["普通最短路径", "19.973 km", "19.973", "congestion, flood", "距离较短，但经过历史洪水影响区。"],
      ["安全路径", "26.816 km", "32.209", "congestion", "距离增加，但绕开主要积水风险。"],
    ],
    note:
      "洪水场景中，普通最短路径同样是 19.973 公里，但是危险类型包含 flood，说明它经过了历史洪水影响区。安全路径为 26.816 公里，避开了主要积水风险，只剩拥堵风险。",
  },
  {
    section: "十二、洪水场景可视化",
    title: "蓝色区域表示历史洪水影响区",
    kind: "map",
    body: "outputs/amap_flood/route_map_amap_static.png",
    note:
      "这一页展示洪水场景的真实高德地图底图叠加图。蓝色半透明区域是历史洪水影响区。普通最短路径直接穿过该区域，安全路径选择绕开，所以更适合救援车辆通行。",
  },
  {
    section: "十三、成果清单",
    title: "数据、源码、图表和汇报材料",
    kind: "cards",
    body: [
      ["数据包", "高德道路数据、历史灾害事件表、道路灾害映射表。"],
      ["源码", "高德数据获取、灾害映射、Dijkstra、结果可视化。"],
      ["图表", "路径对比 CSV、边权重表、地震/洪水简化路线图。"],
      ["汇报", "技术方案、PPT、详细汇报手稿和演示脚本。"],
    ],
    note:
      "项目成果包括四类。第一是数据包，第二是源码，第三是结果图表，第四是汇报材料。这样可以满足任务书中数据包、源码、技术方案、汇报 PPT 和演示录像脚本的要求。",
  },
  {
    section: "十四、创新点与不足",
    title: "从规则标注升级为空间映射",
    kind: "bullets",
    body: [
      "创新点：结合真实地图道路数据和公开历史灾害资料。",
      "创新点：用空间叠加方法自动识别危险道路。",
      "创新点：对比普通最短路径和安全路径，突出救援场景特点。",
      "不足：公开灾害资料通常不是官方逐路段封闭数据，后续可接入更精确的应急数据。",
    ],
    note:
      "项目的主要创新是从简单规则标注，升级为真实灾害影响区和真实道路的空间映射。当然它也有不足，就是公开数据不一定精确到每条道路。后续如果能接入官方道路封闭数据、消防警情或遥感灾害范围，项目会更接近真实业务系统。",
  },
  {
    section: "十五、总结",
    title: "安全路径比最短路径更适合灾害救援",
    kind: "closing",
    body: [
      "真实地图数据提供道路基础。",
      "历史灾害资料提供风险场景依据。",
      "空间叠加把灾害影响转成危险路段。",
      "Dijkstra 用综合权重规划更安全的救援路线。",
    ],
    note:
      "最后总结一下，本项目说明了救援路径规划不能只看距离。我们用高德提供真实道路，用历史灾害资料提供风险依据，再通过空间叠加识别危险路段。Dijkstra 算法在综合权重下会主动绕开风险区域，得到更适合救援的安全路径。",
  },
];

function textbox(slide, text, position, style = {}) {
  const box = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  box.text = text;
  box.text.style = {
    typeface: FONT,
    fontSize: style.fontSize ?? 20,
    color: style.color ?? COLORS.ink,
    bold: style.bold ?? false,
  };
  return box;
}

function rect(slide, position, fill, line = COLORS.line, radius = "rounded-md") {
  return slide.shapes.add({
    geometry: "roundRect",
    position,
    fill,
    line: { style: "solid", fill: line, width: 1 },
    borderRadius: radius,
  });
}

function addHeader(slide, item, index) {
  textbox(slide, item.section, { left: 64, top: 34, width: 520, height: 24 }, { fontSize: 14, color: COLORS.teal, bold: true });
  textbox(slide, item.title, { left: 64, top: 66, width: 980, height: 54 }, { fontSize: 33, color: COLORS.ink, bold: true });
  textbox(slide, `项目14 | ${String(index + 1).padStart(2, "0")}`, { left: 1080, top: 42, width: 140, height: 24 }, { fontSize: 13, color: COLORS.muted });
}

function addFooter(slide) {
  slide.shapes.add({
    geometry: "line",
    position: { left: 64, top: 668, width: 1152, height: 0 },
    line: { style: "solid", fill: COLORS.line, width: 1 },
  });
}

function addBulletList(slide, bullets, left, top, width, fontSize = 22, gap = 58) {
  bullets.forEach((bullet, i) => {
    const y = top + i * gap;
    slide.shapes.add({
      geometry: "ellipse",
      position: { left, top: y + 8, width: 13, height: 13 },
      fill: i % 2 === 0 ? COLORS.blue : COLORS.green,
      line: { style: "solid", fill: "none", width: 0 },
    });
    textbox(slide, bullet, { left: left + 30, top: y, width, height: gap - 4 }, { fontSize, color: COLORS.ink });
  });
}

async function addImage(slide, imagePath, position, alt) {
  const bytes = await fs.readFile(imagePath);
  slide.images.add({
    blob: bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
    contentType: "image/png",
    alt,
    fit: "contain",
    position,
    geometry: "roundRect",
    borderRadius: "rounded-md",
  });
}

async function drawSlide(presentation, item, index) {
  const slide = presentation.slides.add();
  slide.background.fill = COLORS.bg;

  if (item.kind === "cover") {
    slide.background.fill = COLORS.navy;
    textbox(slide, item.section, { left: 76, top: 78, width: 620, height: 28 }, { fontSize: 18, color: "#9EDBD3", bold: true });
    textbox(slide, item.title, { left: 76, top: 145, width: 860, height: 138 }, { fontSize: 52, color: COLORS.white, bold: true });
    item.body.forEach((line, i) => {
      const y = 350 + i * 58;
      slide.shapes.add({ geometry: "ellipse", position: { left: 88, top: y + 8, width: 14, height: 14 }, fill: i === 0 ? COLORS.blue : i === 1 ? COLORS.red : COLORS.green, line: { style: "solid", fill: "none", width: 0 } });
      textbox(slide, line, { left: 118, top: y, width: 760, height: 36 }, { fontSize: 23, color: "#D7E5F0" });
    });
    rect(slide, { left: 920, top: 150, width: 240, height: 330 }, "#203657", "#345172");
    textbox(slide, "真实道路\n历史灾害\n空间叠加\n安全路径", { left: 955, top: 205, width: 170, height: 220 }, { fontSize: 32, color: COLORS.white, bold: true });
    return;
  }

  addHeader(slide, item, index);
  addFooter(slide);

  if (item.kind === "bullets") {
    addBulletList(slide, item.body, 96, 170, 950, 24, 74);
  } else if (item.kind === "cards") {
    item.body.forEach(([title, detail], i) => {
      const x = 82 + i * 286;
      rect(slide, { left: x, top: 180, width: 252, height: 300 }, i % 2 ? COLORS.paleGreen : COLORS.paleBlue);
      textbox(slide, title, { left: x + 22, top: 218, width: 200, height: 36 }, { fontSize: 25, color: i % 2 ? COLORS.green : COLORS.blue, bold: true });
      textbox(slide, detail, { left: x + 22, top: 292, width: 200, height: 120 }, { fontSize: 19, color: COLORS.ink });
    });
  } else if (item.kind === "split") {
    rect(slide, { left: 74, top: 162, width: 520, height: 420 }, COLORS.paleBlue);
    rect(slide, { left: 686, top: 162, width: 520, height: 420 }, COLORS.paleGreen);
    textbox(slide, item.body.leftTitle, { left: 110, top: 196, width: 300, height: 34 }, { fontSize: 26, bold: true, color: COLORS.blue });
    textbox(slide, item.body.rightTitle, { left: 722, top: 196, width: 300, height: 34 }, { fontSize: 26, bold: true, color: COLORS.green });
    addBulletList(slide, item.body.left, 112, 270, 400, 20, 76);
    addBulletList(slide, item.body.right, 724, 270, 400, 20, 76);
  } else if (item.kind === "statement") {
    item.body.forEach((line, i) => {
      const fill = i === 0 ? COLORS.paleBlue : i === 1 ? COLORS.paleRed : COLORS.paleGreen;
      const color = i === 0 ? COLORS.blue : i === 1 ? COLORS.red : COLORS.green;
      rect(slide, { left: 120, top: 165 + i * 132, width: 1040, height: 92 }, fill);
      textbox(slide, line, { left: 160, top: 193 + i * 132, width: 940, height: 34 }, { fontSize: 24, color, bold: true });
    });
  } else if (item.kind === "flow") {
    item.body.forEach((label, i) => {
      const x = 76 + i * 188;
      rect(slide, { left: x, top: 258, width: 148, height: 94 }, i % 2 ? COLORS.paleGreen : COLORS.paleBlue);
      textbox(slide, label, { left: x + 12, top: 288, width: 124, height: 36 }, { fontSize: 19, color: i % 2 ? COLORS.green : COLORS.blue, bold: true });
      if (i < item.body.length - 1) {
        slide.shapes.add({ geometry: "line", position: { left: x + 150, top: 306, width: 34, height: 0 }, line: { style: "solid", fill: COLORS.muted, width: 3, beginArrowType: "none", endArrowType: "triangle" } });
      }
    });
  } else if (item.kind === "table") {
    item.body.forEach(([name, detail], i) => {
      const y = 168 + i * 92;
      rect(slide, { left: 110, top: y, width: 220, height: 64 }, i % 2 ? COLORS.paleGreen : COLORS.paleBlue);
      textbox(slide, name, { left: 142, top: y + 18, width: 160, height: 26 }, { fontSize: 22, color: i % 2 ? COLORS.green : COLORS.blue, bold: true });
      rect(slide, { left: 348, top: y, width: 790, height: 64 }, COLORS.white);
      textbox(slide, detail, { left: 378, top: y + 18, width: 730, height: 26 }, { fontSize: 20, color: COLORS.ink });
    });
  } else if (item.kind === "formula") {
    rect(slide, { left: 100, top: 166, width: 1080, height: 108 }, COLORS.navy);
    textbox(slide, item.body.formula, { left: 136, top: 204, width: 1010, height: 38 }, { fontSize: 31, color: COLORS.white, bold: true });
    addBulletList(slide, item.body.bullets, 126, 338, 960, 21, 58);
  } else if (item.kind === "steps") {
    item.body.forEach((step, i) => {
      const y = 150 + i * 82;
      textbox(slide, `${i + 1}`, { left: 96, top: y, width: 46, height: 46 }, { fontSize: 30, bold: true, color: COLORS.blue });
      rect(slide, { left: 160, top: y - 4, width: 920, height: 58 }, COLORS.white);
      textbox(slide, step, { left: 186, top: y + 12, width: 860, height: 26 }, { fontSize: 19, color: COLORS.ink });
    });
  } else if (item.kind === "comparison") {
    const cards = [
      { row: item.body[0], fill: COLORS.paleBlue, color: COLORS.blue },
      { row: item.body[1], fill: COLORS.paleGreen, color: COLORS.green },
    ];
    cards.forEach(({ row, fill, color }, i) => {
      const y = 168 + i * 210;
      rect(slide, { left: 82, top: y, width: 1080, height: 170 }, fill);
      textbox(slide, row[0], { left: 116, top: y + 28, width: 240, height: 36 }, { fontSize: 27, color, bold: true });
      textbox(slide, `距离 ${row[1]}   综合代价 ${row[2]}`, { left: 400, top: y + 30, width: 480, height: 32 }, { fontSize: 23, color: COLORS.ink, bold: true });
      textbox(slide, `危险类型：${row[3]}`, { left: 400, top: y + 82, width: 460, height: 30 }, { fontSize: 20, color: COLORS.red, bold: true });
      textbox(slide, row[4], { left: 116, top: y + 104, width: 900, height: 32 }, { fontSize: 20, color: COLORS.muted });
    });
  } else if (item.kind === "map") {
    await addImage(slide, path.join(ROOT, item.body), { left: 58, top: 138, width: 880, height: 528 }, "路径规划可视化图");
    rect(slide, { left: 966, top: 170, width: 240, height: 310 }, COLORS.white);
    textbox(slide, "图例重点", { left: 994, top: 198, width: 160, height: 32 }, { fontSize: 24, bold: true, color: COLORS.ink });
    addBulletList(slide, ["蓝色：普通最短路径", "绿色：安全路径", "半透明区：历史灾害影响区", "细线：受影响道路"], 994, 260, 170, 17, 54);
  } else if (item.kind === "closing") {
    item.body.forEach((line, i) => {
      const fill = [COLORS.paleBlue, COLORS.paleGreen, COLORS.paleOrange, COLORS.paleRed][i];
      const color = [COLORS.blue, COLORS.green, COLORS.orange, COLORS.red][i];
      rect(slide, { left: 150, top: 150 + i * 118, width: 940, height: 74 }, fill);
      textbox(slide, line, { left: 190, top: 172 + i * 118, width: 840, height: 30 }, { fontSize: 24, bold: true, color });
    });
  }
}

function buildManuscript() {
  const header = [
    "# 项目14：避开危险路段的救援路径规划详细汇报手稿",
    "",
    "建议汇报时长：12-18 分钟。",
    "使用方式：每页 PPT 对应一段讲稿，正式汇报时可根据时间删减。",
    "",
  ].join("\n");
  const parts = slides.map((slide, index) => {
    return [
      `## 第 ${index + 1} 页：${slide.title}`,
      "",
      `【页面重点】${slide.section}`,
      "",
      `【讲稿】${slide.note}`,
      "",
    ].join("\n");
  });
  const ending = [
    "## 备用答辩说明",
    "",
    "1. 如果老师问地图数据来源：道路名称、距离、路线坐标和交通状态来自高德 Web 服务路径规划接口。",
    "2. 如果老师问灾害数据来源：地震采用 1679 年三河-平谷地震公开历史资料；洪水采用 2012 年北京 7·21 特大暴雨和中国气象数据服务资料。",
    "3. 如果老师问为什么不是官方逐路段灾情：公开历史资料通常没有逐路段封闭数据，所以项目采用影响区缓冲和道路叠加的方法，这是课程项目中合理的建模方法。",
    "4. 如果老师问为什么安全路径更长：安全路径优化目标不是距离最短，而是综合代价最低，高风险路段权重变大后，算法会选择绕行。",
    "5. 如果老师问为什么只用 Dijkstra：本项目边权重均为非负数，Dijkstra 可以稳定求出从起点到终点的最小代价路径，原理清晰，适合课程展示。",
    "",
  ].join("\n");
  return header + parts.join("\n") + ending;
}

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });
  await fs.rm(PREVIEW_DIR, { recursive: true, force: true });
  await fs.rm(LAYOUT_DIR, { recursive: true, force: true });
  await fs.rm(QA_DIR, { recursive: true, force: true });
  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  await fs.mkdir(LAYOUT_DIR, { recursive: true });
  await fs.mkdir(QA_DIR, { recursive: true });

  const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
  for (let i = 0; i < slides.length; i++) {
    await drawSlide(presentation, slides[i], i);
  }

  await fs.writeFile(path.join(SCRATCH, "source-notes.txt"), [
    "AMap Web Service direction API: road route geometry, names, distance, traffic status.",
    "data/historical_disasters/disaster_events.csv: historical disaster event records.",
    "data/amap_earthquake/road_disaster_mapping.csv: earthquake road overlay mapping.",
    "data/amap_flood/road_disaster_mapping.csv: flood road overlay mapping.",
    "outputs/amap_earthquake/path_comparison.csv and outputs/amap_flood/path_comparison.csv: route result metrics.",
  ].join("\n"), "utf-8");
  await fs.writeFile(path.join(SCRATCH, "slide-plan.txt"), [
    "Create mode. Dijkstra-only course presentation.",
    "Palette: navy #18213A, route blue #1F5EFF, safety green #178A4A, risk red #D64545, warning orange #E58B25.",
    "Typography: Microsoft YaHei headings/body.",
    "Layout: editable shapes and text, embedded clean map PNGs for route evidence.",
  ].join("\n"), "utf-8");

  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(path.join(PREVIEW_DIR, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 1 }));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(LAYOUT_DIR, `${stem}.layout.json`), await layout.text(), "utf-8");
  }
  await writeBlob(path.join(PREVIEW_DIR, "deck-montage.webp"), await presentation.export({ format: "webp", montage: true, scale: 1 }));

  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(PPTX_PATH);
  await fs.writeFile(MANUSCRIPT_MD, buildManuscript(), "utf-8");
  await fs.writeFile(path.join(QA_DIR, "visual-qa.txt"), [
    `Rendered all ${slides.length} slides to PNG and montage.`,
    "Checked slide count, Dijkstra-only wording, historical disaster data wording, and AMap static basemap inclusion.",
    "Final PPTX uses editable text and shapes plus embedded real-map route images.",
  ].join("\n"), "utf-8");

  console.log(JSON.stringify({ pptx: PPTX_PATH, manuscript: MANUSCRIPT_MD, preview: PREVIEW_DIR }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
