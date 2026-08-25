// QD14 osm_sichuan_earthquake 合成 edges.csv 重建器 v2
// 节点沿道路呈线状聚集，固定邻域搜不到邻居 —— 改用半径倍增 NN +
// 连通块代表节点合并，保证全图连通，最后用规划器同款权重公式 Dijkstra 自检。
const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const OUT = path.join(DIR, 'edges.csv');

const START_COORD = [104.0657, 30.6598];  // 成都市区
const TARGET_COORD = [103.6215, 31.0928]; // 汶川县城

// ---------- 解析 nodes.csv ----------
console.time('parse nodes');
const nodeIds = [];
const xs = [], ys = [];
{
  const txt = fs.readFileSync(path.join(DIR, 'nodes.csv'), 'latin1');
  const lines = txt.split('\n');
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const c1 = line.indexOf(',');
    const c2 = line.indexOf(',', c1 + 1);
    const c3 = line.indexOf(',', c2 + 1);
    nodeIds.push(line.slice(0, c1));
    xs.push(parseFloat(line.slice(c1 + 1, c2)));
    ys.push(parseFloat(line.slice(c2 + 1, c3 < 0 ? line.length : c3)));
  }
}
const N = nodeIds.length;
const idxOf = new Map();
for (let i = 0; i < N; i++) idxOf.set(nodeIds[i], i);
console.timeEnd('parse nodes');
console.log('nodes:', N);

// ---------- 解析映射 ----------
console.time('parse mappings');
const disasterEdges = [];
{
  const txt = fs.readFileSync(path.join(DIR, 'road_disaster_mapping.csv'), 'utf8');
  const lines = txt.split('\n');
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const f = line.split(',');
    const eid = f[0], from = f[1], to = f[2], road = f[3], danger = f[7];
    const a = idxOf.get(from), b = idxOf.get(to);
    if (a === undefined || b === undefined || a === b) continue;
    disasterEdges.push({ eid, a: Math.min(a, b), b: Math.max(a, b), road, danger });
  }
}
const trafficCong = new Map();
const trafficEdges = [];
{
  const txt = fs.readFileSync(path.join(DIR, 'road_traffic_mapping.csv'), 'utf8');
  const lines = txt.split('\n');
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const f = line.split(',');
    const eid = f[0], from = f[1], to = f[2], road = f[3], cong = parseFloat(f[9]);
    trafficCong.set(eid, isNaN(cong) ? 0.1 : cong);
    const a = idxOf.get(from), b = idxOf.get(to);
    if (a === undefined || b === undefined || a === b) continue;
    trafficEdges.push({ eid, a: Math.min(a, b), b: Math.max(a, b), road });
  }
}
console.timeEnd('parse mappings');
console.log('disaster edges:', disasterEdges.length, '| traffic edges:', trafficEdges.length);

// ---------- 网格 + 半径倍增最近邻 ----------
const CELL = 0.01;
const cellKey = (cx, cy) => cx * 100000 + cy;
const grid = new Map();
for (let i = 0; i < N; i++) {
  const k = cellKey(Math.floor(xs[i] / CELL), Math.floor(ys[i] / CELL));
  let arr = grid.get(k);
  if (!arr) grid.set(k, arr = []);
  arr.push(i);
}
// 半径 r 的方环内找最近邻（只扫环，不重扫内部）
function nearestInRing(i, r, skip) {
  const cx = Math.floor(xs[i] / CELL), cy = Math.floor(ys[i] / CELL);
  let best = -1, bestD = Infinity;
  for (let dx = -r; dx <= r; dx++) {
    for (let dy = -r; dy <= r; dy++) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue; // 只扫方环
      const arr = grid.get(cellKey(cx + dx, cy + dy));
      if (!arr) continue;
      for (const j of arr) {
        if (j === i || (skip && skip(j))) continue;
        const ddx = xs[i] - xs[j], ddy = ys[i] - ys[j];
        const d = ddx * ddx + ddy * ddy;
        if (d < bestD) { bestD = d; best = j; }
      }
    }
  }
  return best === -1 ? null : { j: best, d2: bestD };
}
function nearestExpanding(i, maxR, skip) {
  for (let r = 1; r <= maxR; r++) {
    const t = nearestInRing(i, r, skip);
    if (t) return t;
  }
  return null;
}

// ---------- 边集合 ----------
console.time('NN edges');
const edgeMap = new Map();
const ekey = (a, b) => a + '_' + b;
function addEdge(a, b, attrs) {
  const k = ekey(a, b);
  let e = edgeMap.get(k);
  if (!e) { e = { a, b, eid: null, danger: 'normal', cong: null, road: '', kind: 'nn' }; edgeMap.set(k, e); }
  Object.assign(e, attrs);
  return e;
}
for (const d of disasterEdges) addEdge(d.a, d.b, { eid: d.eid, danger: d.danger, road: d.road, kind: 'disaster' });
for (const t of trafficEdges) {
  const k = ekey(t.a, t.b);
  let e = edgeMap.get(k);
  if (!e) e = addEdge(t.a, t.b, { eid: t.eid, road: t.road, kind: 'traffic' });
  else if (!e.eid) { e.eid = t.eid; e.kind = 'traffic'; }
  if (trafficCong.has(t.eid)) e.cong = trafficCong.get(t.eid);
}
// 每个节点找最近邻（半径倍增至 64），有必要的节点补第二近邻
let noNN = 0;
for (let i = 0; i < N; i++) {
  const t = nearestExpanding(i, 64);
  if (!t) { noNN++; continue; }
  const a = Math.min(i, t.j), b = Math.max(i, t.j);
  if (!edgeMap.has(ekey(a, b))) addEdge(a, b, {});
}
console.timeEnd('NN edges');
console.log('edges after NN:', edgeMap.size, '| nodes without any neighbor:', noNN);

// ---------- 并查集 + 分阶段连通块合并 ----------
console.time('connectivity');
const parent = new Int32Array(N);
for (let i = 0; i < N; i++) parent[i] = i;
function find(x) { let r = x; while (parent[r] !== r) r = parent[r]; while (parent[x] !== r) { const nx = parent[x]; parent[x] = r; x = nx; } return r; }
function union(a, b) { const ra = find(a), rb = find(b); if (ra !== rb) parent[rb] = ra; }
for (const e of edgeMap.values()) union(e.a, e.b);

function components() {
  const reps = new Map(); // root -> representative node
  const sizes = new Map();
  for (let i = 0; i < N; i++) {
    const r = find(i);
    if (!reps.has(r)) reps.set(r, i);
    sizes.set(r, (sizes.get(r) || 0) + 1);
  }
  return { reps, sizes };
}
let { reps, sizes } = components();
let giantRoot = -1, giantSize = 0;
for (const [r, s] of sizes) if (s > giantSize) { giantSize = s; giantRoot = r; }
console.log('components after NN:', reps.size, '| giant:', giantSize);

// 阶段一：每个非 giant 连通块，从代表节点向外倍增找"不同连通块"的最近节点，连边
let rounds = 0;
while (reps.size > 1 && rounds < 12) {
  rounds++;
  let merged = 0;
  for (const [r, rep] of reps) {
    if (r === giantRoot) continue;
    const myRoot = find(rep);
    if (myRoot === giantRoot) continue; // 已被本轮前面的合并带入
    const t = nearestExpanding(rep, 200, j => find(j) === myRoot);
    if (t) {
      addEdge(Math.min(rep, t.j), Math.max(rep, t.j), { kind: 'bridge' });
      union(rep, t.j);
      merged++;
    }
  }
  ({ reps, sizes } = components());
  for (const [r, s] of sizes) if (s > giantSize) { giantSize = s; giantRoot = r; }
  console.log(`  merge round ${rounds}: merged ${merged}, components left ${reps.size}, giant ${giantSize}`);
  if (merged === 0) break;
}
// 阶段二：兜底——残余块直接连代表节点的任意最近邻
if (reps.size > 1) {
  for (const [r, rep] of reps) {
    if (find(rep) === find(0)) continue;
    const t = nearestExpanding(rep, 200);
    if (t) { addEdge(Math.min(rep, t.j), Math.max(rep, t.j), { kind: 'bridge' }); union(rep, t.j); }
  }
  ({ reps } = components());
}
console.timeEnd('connectivity');
console.log('final components:', reps.size);

// ---------- START/TARGET 连接 ----------
function nearestK(coord, k) {
  const cx = Math.floor(coord[0] / CELL), cy = Math.floor(coord[1] / CELL);
  const cand = [];
  for (let dx = -2; dx <= 2; dx++) for (let dy = -2; dy <= 2; dy++) {
    const arr = grid.get(cellKey(cx + dx, cy + dy));
    if (!arr) continue;
    for (const j of arr) {
      const ddx = xs[j] - coord[0], ddy = ys[j] - coord[1];
      cand.push({ j, d: ddx * ddx + ddy * ddy });
    }
  }
  cand.sort((p, q) => p.d - q.d);
  return cand.slice(0, k);
}
const startNodes = nearestK(START_COORD, 5);
const targetNodes = nearestK(TARGET_COORD, 5);
const connectors = [];
let connIdx = 0;
for (const c of startNodes) connectors.push({ eid: 'CONN' + String(++connIdx).padStart(4, '0'), a: 'START', b: c.j, sx: START_COORD[0], sy: START_COORD[1], road: 'start connector' });
for (const c of targetNodes) connectors.push({ eid: 'CONN' + String(++connIdx).padStart(4, '0'), a: 'TARGET', b: c.j, sx: TARGET_COORD[0], sy: TARGET_COORD[1], road: 'target connector' });

// ---------- 属性与输出 ----------
const R = 6371.0088;
function haversine(ax, ay, bx, by) {
  const toR = Math.PI / 180;
  const dLat = (by - ay) * toR, dLon = (bx - ax) * toR;
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(ay * toR) * Math.cos(by * toR) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}
function hashFrac(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return ((h >>> 0) % 10000) / 10000;
}
const edges = [...edgeMap.values()];
let synCounter = 0;
for (const e of edges) {
  if (!e.eid) e.eid = 'SYN' + String(++synCounter).padStart(7, '0');
  e.dist = haversine(xs[e.a], ys[e.a], xs[e.b], ys[e.b]);
  if (e.dist < 1e-5) e.dist = 0.0001;
  if (e.cong === null) {
    const c = trafficCong.get(e.eid);
    e.cong = c !== undefined ? c : Math.round((0.03 + 0.09 * hashFrac(e.eid)) * 1000) / 1000;
  }
}
for (const c of connectors) {
  c.dist = Math.max(0.0001, haversine(c.sx, c.sy, xs[c.b], ys[c.b]));
  c.cong = 0.05;
}
console.time('write');
const out = ['edge_id,from,to,distance,danger_type,congestion,passable,road_name,instruction,polyline,strategy,variant,path_index,step_index'];
let step = 0;
const esc = (v) => /[",\n]/.test(String(v)) ? '"' + String(v).replace(/"/g, '""') + '"' : v;
for (const e of edges) {
  const poly = xs[e.a].toFixed(7) + ',' + ys[e.a].toFixed(7) + ';' + xs[e.b].toFixed(7) + ',' + ys[e.b].toFixed(7);
  const instr = e.kind === 'disaster' ? 'OSM way segment (disaster-mapped)' : e.kind === 'traffic' ? 'OSM way segment (traffic-mapped)' : e.kind === 'bridge' ? 'synthetic bridge segment' : 'synthetic nearest-neighbor segment';
  out.push([e.eid, nodeIds[e.a], nodeIds[e.b], e.dist.toFixed(4), e.danger, e.cong.toFixed(3), 'true', e.road || '', instr, poly, 'osm', '', 0, step++].map(esc).join(','));
}
for (const c of connectors) {
  const poly = c.sx.toFixed(7) + ',' + c.sy.toFixed(7) + ';' + xs[c.b].toFixed(7) + ',' + ys[c.b].toFixed(7);
  out.push([c.eid, c.a, nodeIds[c.b], c.dist.toFixed(4), 'normal', c.cong.toFixed(3), 'true', c.road, c.road + ' (synthetic)', poly, 'connector', 'connector', 0, step++].map(esc).join(','));
}
fs.writeFileSync(OUT, '\ufeff' + out.join('\n') + '\n', 'utf8');
console.timeEnd('write');
const stat = { disaster: 0, traffic: 0, nn: 0, bridge: 0 };
for (const e of edges) stat[e.kind] = (stat[e.kind] || 0) + 1;
console.log('edges.csv:', edges.length, 'roads +', connectors.length, 'connectors |', (fs.statSync(OUT).size / 1048576).toFixed(1), 'MB | kinds:', JSON.stringify(stat));

// ---------- Dijkstra 自检（与 rescue_planner.py 同款公式） ----------
console.time('dijkstra');
const risk = { normal: 1, congestion: 1.4, flood: 2.2, collapse: 8 };
const CW = 0.6;
const adj = new Map();
function link(u, v, w, d, dg) { let a = adj.get(u); if (!a) adj.set(u, a = []); a.push([v, w, d, dg]); }
const sid = N + 1, tid = N + 2;
for (const e of edges) {
  const w = e.dist * risk[e.danger] * (1 + CW * e.cong);
  link(e.a, e.b, w, e.dist, e.danger);
  link(e.b, e.a, w, e.dist, e.danger);
}
for (const c of connectors) {
  const u = c.a === 'START' ? sid : tid;
  const w = c.dist * (1 + CW * c.cong);
  link(u, c.b, w, c.dist, 'normal');
  link(c.b, u, w, c.dist, 'normal');
}
const distArr = new Float64Array(N + 3).fill(Infinity);
const prevArr = new Int32Array(N + 3).fill(-1);
distArr[sid] = 0;
class Heap {
  constructor() { this.a = []; }
  push(x) { const a = this.a; a.push(x); let i = a.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (a[p][0] <= a[i][0]) break; [a[p], a[i]] = [a[i], a[p]]; i = p; } }
  pop() { const a = this.a; const top = a[0]; const last = a.pop(); if (a.length) { a[0] = last; let i = 0; for (;;) { const l = 2 * i + 1, r = l + 1; let m = i; if (l < a.length && a[l][0] < a[m][0]) m = l; if (r < a.length && a[r][0] < a[m][0]) m = r; if (m === i) break; [a[m], a[i]] = [a[i], a[m]]; i = m; } } return top; }
  get size() { return this.a.length; }
}
const heap = new Heap();
heap.push([0, sid]);
while (heap.size) {
  const [d, u] = heap.pop();
  if (d > distArr[u]) continue;
  if (u === tid) break;
  const nb = adj.get(u);
  if (!nb) continue;
  for (const [v, w] of nb) if (d + w < distArr[v]) { distArr[v] = d + w; prevArr[v] = u; heap.push([distArr[v], v]); }
}
console.timeEnd('dijkstra');
if (distArr[tid] === Infinity) { console.error('!!! START 无法到达 TARGET'); process.exit(1); }
let u = tid, hops = 0, km = 0, dangerCount = 0;
const dangerSeen = new Set();
while (u !== sid && u !== -1) {
  const p = prevArr[u];
  const nb = adj.get(p);
  let best = null;
  for (const e of nb) if (e[0] === u && (!best || e[1] < best[1])) best = e;
  if (!best) break;
  km += best[2];
  if (best[3] !== 'normal') { dangerCount++; dangerSeen.add(best[3]); }
  hops++; u = p;
}
console.log('=== 自检通过 ===');
console.log('safe 模式总代价:', distArr[tid].toFixed(3));
console.log('路径边数:', hops, '| 总距离:', km.toFixed(3), 'km | 危险边:', dangerCount, [...dangerSeen].join(','));
