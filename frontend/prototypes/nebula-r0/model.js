export const palette = ['#57e3bf', '#eab56e', '#a996f7', '#72c8f3', '#ea8eb5', '#b4d87d', '#f18c6e', '#82a6f5'];
export const typeColors = { job: '#87c7ff', skill: '#57e3bf', industry: '#c6a0ee' };
export const typeNames = { job: '岗位', skill: '技能', industry: '场景' };
export function communityColor(id) {
  return id ? palette[(Number(id.slice(1)) - 1) % palette.length] : '#adb5c9';
}
export function makeIndex(data) {
  const byId = new Map(data.nodes.map(n => [n.nodeId, n]));
  const adjacent = new Map(data.nodes.map(n => [n.nodeId, []]));
  if (byId.size !== data.nodes.length) throw new Error('重复实体 ID');
  for (const e of data.edges) {
    if (!byId.has(e.source) || !byId.has(e.target)) throw new Error('关系端点缺失');
    adjacent.get(e.source).push(e);
    adjacent.get(e.target).push(e);
  }
  return { byId, adjacent };
}
export function search(nodes, query, types) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return nodes.filter(n => types[n.type] && (n.label.toLowerCase().includes(q) || n.nodeId.toLowerCase().includes(q)))
    .sort((a, b) => Number(b.label.toLowerCase() === q) - Number(a.label.toLowerCase() === q) || (a.nodeId < b.nodeId ? -1 : a.nodeId > b.nodeId ? 1 : 0));
}
export function radius(node, zoom, cap, selected = false) {
  const base = node.type === 'job' ? 2.4 : node.visibleLevel === 1 ? 1.6 : node.type === 'industry' ? 1 : .85;
  return Math.min(cap, Math.max(selected ? 4 : .8, base * Math.sqrt(Math.max(.1, zoom))));
}
export function rotate(xyz, view) {
  const [x, y, z] = xyz;
  const xx = x * Math.cos(view.yaw) + z * Math.sin(view.yaw);
  const zz = -x * Math.sin(view.yaw) + z * Math.cos(view.yaw);
  return [xx, y * Math.cos(view.pitch) - zz * Math.sin(view.pitch), y * Math.sin(view.pitch) + zz * Math.cos(view.pitch)];
}
export function project(xyz, view) {
  const p = rotate(xyz, view);
  return [p[0] * view.k + view.x, p[1] * view.k + view.y, p[2]];
}
export function fit(nodes, width, height, view) {
  const points = nodes.map(n => rotate(n.xyz, view));
  if (!points.length) return { ...view };
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const k = Math.min((width - 100) / Math.max(150, x1 - x0), (height - 110) / Math.max(150, y1 - y0));
  return { ...view, k, x: width / 2 - (x0 + x1) / 2 * k, y: height / 2 - (y0 + y1) / 2 * k };
}
export function visibleNodes(data, state, index) {
  const connected = new Set();
  if (state.selected) for (const e of index.adjacent.get(state.selected) || []) { connected.add(e.source); connected.add(e.target); }
  const level = state.zoom >= 3.5 ? 2 : state.zoom >= 1.6 ? 1 : 0;
  const matches = new Set(state.matches);
  return data.nodes.filter(n => state.types[n.type] && (n.visibleLevel <= level || n.nodeId === state.selected || connected.has(n.nodeId) || matches.has(n.nodeId)));
}
export function labelBoxes(candidates, width, height, density = 1) {
  const boxes = [], ids = new Set();
  for (const c of [...candidates].sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id))) {
    const box = { x: c.x + 9, y: c.y - 12, w: c.width + 8, h: 20 };
    if (box.x < 0 || box.y < 0 || box.x + box.w > width || box.y + box.h > height) continue;
    const margin = density === 0 ? 25 : density === 2 ? 2 : 10;
    if (boxes.some(b => box.x < b.x + b.w + margin && box.x + box.w + margin > b.x && box.y < b.y + b.h + margin && box.y + box.h + margin > b.y)) continue;
    boxes.push(box); ids.add(c.id);
  }
  return ids;
}
export function dust(communities, count = 18000) {
  let seed = 24;
  const rand = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296);
  const major = communities.filter(c => c.jobCount > 1);
  const total = major.reduce((s, c) => s + c.jobCount, 0);
  const result = [];
  for (const c of major) {
    const amount = Math.floor(count * c.jobCount / total);
    for (let i = 0; i < amount; i++) {
      const r = Math.sqrt(-2 * Math.log(Math.max(.00001, rand()))) * c.radius * .67;
      const a = rand() * Math.PI * 2;
      result.push({ xyz: [c.center[0] + Math.cos(a) * r * 1.35, c.center[1] + Math.sin(a) * r * .85, c.center[2] + (rand() - .5) * c.radius * 1.2], color: communityColor(c.id), alpha: .09 + rand() * .35, size: .4 + rand() * 1.1 });
    }
  }
  return result;
}
