import { Vector3 } from 'three'
import type { GraphNode } from '../../api/graph'
import type { Point } from '../nebulaViewport'

export const DEPTH_VERSION='display-depth-v1'
// Display separation only: neither depth nor Euclidean distance is a semantic score.
export function spatialPoint(node:Pick<GraphNode,'id'|'kind'>,point:Point) {
 let hash=2166136261
 for(const char of node.id)hash=Math.imul(hash^char.charCodeAt(0),16777619)
 const radius=Math.hypot(point.x,point.y)/30
 return new Vector3(point.x/30,((hash>>>0)/4294967296-.5)*(7+8*Math.exp(-radius*radius/900)),point.y/30)
}
