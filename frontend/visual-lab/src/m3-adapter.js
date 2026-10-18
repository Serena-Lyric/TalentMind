import { spiralPoint } from './config.js';

const kinds = { job: 0, skill: 2, industry: 3 };
const relations = new Set(['REQUIRES', 'APPLIES_TO', 'RELATED_TO']);
function hash(text) {
  let value = 2166136261;
  for (const char of text) value = Math.imul(value ^ char.codePointAt(0), 16777619);
  return value >>> 0;
}

export function adaptM3(input) {
  if (!input || !Array.isArray(input.nodes) || !Array.isArray(input.edges)) throw new Error('M3 requires nodes/edges arrays');
  const ids = new Set(), nodeKinds = { job: 0, skill: 0, industry: 0 }, edgeKinds = { REQUIRES: 0, APPLIES_TO: 0, RELATED_TO: 0 };
  const nodes = input.nodes.map((raw, sourceIndex) => {
    if (!raw || typeof raw.id !== 'string' || !raw.id.trim() || ids.has(raw.id)) throw new Error(`Invalid/duplicate node ID at nodes[${sourceIndex}]`);
    const kind = raw.type;
    if (typeof kind !== 'string' || !Object.hasOwn(kinds, kind) || (raw.kind && raw.kind !== kind)) throw new Error(`Unknown/inconsistent node kind at nodes[${sourceIndex}]`);
    ids.add(raw.id); nodeKinds[kind]++;
    const h = hash(raw.id), radius = 22 + (h % 6800) / 100;
    const position = spiralPoint(radius, h % 4, ((h >>> 8) % 1000 / 1000 - .5) * .26);
    position[1] = ((h >>> 16) % 1000 / 1000 - .5) * 9;
    return { id: raw.id, name: raw.name_zh || raw.display_name || raw.name || raw.id, kind, type: kinds[kind], families: [], demo: false, position, raw, sourceIndex };
  });
  const edges = input.edges.map((raw, sourceIndex) => {
    if (!raw || !ids.has(raw.source) || !ids.has(raw.target) || !relations.has(raw.type)) throw new Error(`Invalid endpoint/relation at edges[${sourceIndex}]`);
    edgeKinds[raw.type]++;
    return { source: raw.source, target: raw.target, kind: raw.type, raw, sourceIndex };
  });
  const byId = new Map(nodes.map(node => [node.id, node])), anchors = new Map();
  for (const edge of edges) {
    const a = byId.get(edge.source), b = byId.get(edge.target);
    const job = a.kind === 'job' ? a : b.kind === 'job' ? b : null;
    const other = job === a ? b : a;
    if (job && other.kind !== 'job') {
      if (!anchors.has(other.id)) anchors.set(other.id, new Map());
      anchors.get(other.id).set(job.id, job.position);
    }
  }
  for (const node of nodes) {
    const positions = anchors.get(node.id);
    if (!positions) continue;
    const values = [...positions.values()], h = hash(node.id);
    node.position = [0, 1, 2].map(axis => values.reduce((sum, p) => sum + p[axis], 0) / values.length + (((h >>> (axis * 8)) % 256) / 255 - .5) * (axis === 1 ? 8 : 16));
  }
  return { nodes, edges, provenance: { source: 'exchange/m3/graph.json', mode: 'formal-handover-snapshot', nodeKinds, edgeKinds, layout: 'identity-hash-and-adjacency-display-only' } };
}

export function filterGraph(graph, { kind = 'all', relation = 'all', query = '', focus = null } = {}) {
  const neighbors = focus ? new Set([focus]) : null;
  if (neighbors) for (const edge of graph.edges) {
    if (edge.source === focus) neighbors.add(edge.target);
    if (edge.target === focus) neighbors.add(edge.source);
  }
  const text = query.trim().toLocaleLowerCase();
  const nodeIds = new Set(graph.nodes.filter(node =>
    (kind === 'all' || node.kind === kind) && (!neighbors || neighbors.has(node.id)) &&
    (!text || `${node.id} ${node.name} ${node.raw?.name_en ?? ''}`.toLocaleLowerCase().includes(text))
  ).map(node => node.id));
  const edgeIndices = graph.edges.flatMap((edge, index) => nodeIds.has(edge.source) && nodeIds.has(edge.target) && (relation === 'all' || edge.kind === relation) ? [index] : []);
  return { nodeIds, edgeIndices };
}
