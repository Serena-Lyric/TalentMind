import { get, post } from '../utils/request'
import type { Analysis } from './m2'

export interface CandidateSource { analysis_sha256:string; analysis:Analysis }
export interface WorkCandidates {
  state:{ binding:{registry_id:string; revision:number; sha256:string}; candidates:Record<string,any>; relations:Record<string,any>; [key:string]:any }
  versions:number[]
  relation_sha256s:Record<string,string>
  sources:CandidateSource[]
}
export interface SkillCandidateDetail {
  candidate:Record<string,any>
  versions:number[]
  projection:Record<string,any>|null
  projection_scope:'historical_candidate_only'|'current_head'
  eligible_new_evidence:CandidateSource[]
}
export interface PendingMaintenance {id:string;kind:'work'|'skill';candidate_id?:string;request_sha256:string;request?:Record<string,any>;can_close?:boolean}
export interface ClosedMaintenance {status:'closed_incomplete';reason:string;candidate_version_saved:boolean;projection_binding:'not_recorded'}
export interface ClosedMaintenanceRecord extends ClosedMaintenance {id:string;kind:'work'|'skill';candidate_id?:string}
const root='/m2/delivery/candidates'
export const getPendingMaintenance=()=>get<{items:PendingMaintenance[];closed?:ClosedMaintenanceRecord[]}>(`${root}/pending`)
export const resumeMaintenance=(id:string)=>post<WorkCandidates|SkillCandidateDetail>(`${root}/pending/${encodeURIComponent(id)}/resume`,{})
export const closeMaintenance=(id:string,reason:string)=>post<ClosedMaintenance>(`${root}/pending/${encodeURIComponent(id)}/close`,{reason})
export const getWorkCandidates=(revision?:number)=>get<WorkCandidates>(`${root}/work`,{revision})
export const saveWorkCandidates=(request:Record<string,any>)=>post<WorkCandidates>(`${root}/work/batches`,request)
export const getSkillCandidates=()=>get<{items:Record<string,any>[]}>(`${root}/skills`)
export const getSkillCandidate=(id:string,version?:number)=>get<SkillCandidateDetail>(`${root}/skills/${encodeURIComponent(id)}`,{version})
export const saveSkillCandidate=(id:string,request:Record<string,any>)=>post<SkillCandidateDetail>(`${root}/skills/${encodeURIComponent(id)}/actions`,request)
