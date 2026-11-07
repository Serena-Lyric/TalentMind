import { get, post } from '../utils/request'
export interface Evidence { namespace:string; jd_id:string; fingerprint:string; field:string; start:number; end:number; quote:string }
export interface Requirement { state:string; target:string; category:string|null; members:string[]; combination:string; open_set:boolean; degree:string|null; degree_polarity:string|null; condition:string|null; reason:string; scope_evidence:Evidence[] }
export interface Claim { id:string; kind:string; text:string; evidence:Evidence[]; requirement:Requirement|null; core:boolean|null; reason:string }
export interface Analysis { namespace:string; jd_id:string; input_row:Record<string,any>; input_sha256:string; input_version:string; analyzer:Record<string,any>; model:Record<string,any>; prompt:Record<string,any>; configuration:Record<string,any>; outcome:string; coverage:Record<string,{status:string;reason:string}>; claims:Claim[]; relations:Record<string,any>[]; semantic_review:string }
export interface DeliveryItem { index:number; namespace:string; jd_id:string; status:string; reason?:string; analysis:Analysis|null; analysis_sha256?:string; row?:Record<string,any>; input?:Record<string,any>; alignment?:Record<string,any>|null; roles?:Record<string,any>|null; role_assignment?:Record<string,any>; skill_candidates?:Record<string,any>[]|null; knowledge_projection?:Record<string,any>|null; reuse?:Record<string,any>; observation?:string; [key:string]:any }
export interface DeliveryRun { run_id:string; status:string; request_sha256:string; created_at?:string; reason?:string; counts:Record<string,number>; items:DeliveryItem[]; knowledge?:Record<string,any>; dependencies?:Record<string,any>; work?:Record<string,any>|null; [key:string]:any }
export interface DeliveryHistory { run_id:string; status:string; created_at?:string; request_sha256?:string; reason?:string; [key:string]:any }
export interface DeliveryInput { jd_id:number; id?:number; title?:string; job_title?:string; source?:string; raw_text?:string; [key:string]:any }
const path=(id:string)=>`/m2/delivery/runs/${encodeURIComponent(id)}`
export const getDeliveryInputs=(offset=0,limit=20)=>get<{items:DeliveryInput[];total:number}>('/m2/delivery/inputs',{offset,limit})
export const getDeliveryRuns=()=>get<DeliveryHistory[]>('/m2/delivery/runs')
export const createDeliveryRun=(selection:{jd_ids:number[]})=>post<DeliveryRun>('/m2/delivery/runs',selection,{timeout:60000})
export const getDeliveryRun=(id:string)=>get<DeliveryRun>(path(id))
export const startDeliveryRun=(id:string)=>post<DeliveryRun>(`${path(id)}/start`,{})
export const stopDeliveryRun=(id:string)=>post<DeliveryRun>(`${path(id)}/stop`,{})
export const resumeDeliveryRun=(id:string)=>post<DeliveryRun>(`${path(id)}/resume`,{})
export const abandonDeliveryRun=(id:string)=>post<DeliveryRun>(`${path(id)}/abandon`,{})
export const getDeliveryGraph=(id:string)=>get<{run_id:string;url:string}>(`${path(id)}/graph`,undefined,{timeout:60000})
// 旧版本只读：保留原结果、原输入和审核历史，不能从此入口重新执行。
export const getM2Runs=()=>get<DeliveryHistory[]>('/m2/runs')
export const getM2Run=(id:string)=>get<Record<string,any>>(`/m2/runs/${encodeURIComponent(id)}`)
export const getM2Item=(id:string,ordinal:number)=>get<Record<string,any>>(`/m2/runs/${encodeURIComponent(id)}/items/${ordinal}`)
