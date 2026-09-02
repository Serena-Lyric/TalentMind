import { defineStore } from 'pinia'
import type { RecommendedJob } from '../api/resume'

export const useResumeStore = defineStore('resume', {
  state: () => ({
    profile: null as any,
    matchResult: null as any,
    recommendedJobs: [] as RecommendedJob[],
    parseQuality: 0,
    fileName: '',
  }),
  actions: {
    setParsed(profile: any, matchResult: any, recommendedJobs: RecommendedJob[] = [], parseQuality = 0, fileName = '') {
      this.profile = profile
      this.matchResult = matchResult
      this.recommendedJobs = recommendedJobs
      this.parseQuality = parseQuality
      this.fileName = fileName
    },
    clear() {
      this.profile = null
      this.matchResult = null
      this.recommendedJobs = []
      this.parseQuality = 0
      this.fileName = ''
    },
  },
})