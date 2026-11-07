import { defineStore } from 'pinia'
import type { RecommendedJob } from '../api/resume'

export const useResumeStore = defineStore('resume', {
  state: () => ({
    revision: 0,
    learningTarget: null as { id: string; requirements_version: string } | null,
    profile: null as any,
    matchResult: null as any,
    recommendedJobs: [] as RecommendedJob[],
    parseQuality: 0,
    fileName: '',
  }),
  actions: {
    setParsed(profile: any, matchResult: any, recommendedJobs: RecommendedJob[] = [], parseQuality = 0, fileName = '') {
      this.learningTarget = null
      this.profile = profile
      this.matchResult = matchResult
      this.recommendedJobs = recommendedJobs
      this.parseQuality = parseQuality
      this.fileName = fileName
    },
    selectTarget(id: string, requirements_version: string) { this.learningTarget = { id, requirements_version } },
    clear() {
      this.profile = null
      this.learningTarget = null
      this.matchResult = null
      this.recommendedJobs = []
      this.parseQuality = 0
      this.fileName = ''
      this.revision++
    },
  },
})