import { onUnmounted, ref, watch } from 'vue'
import { getJobList, type Job } from '../api/jobs'

/** 只读目录浏览。搜索和翻页复用已有后端筛选/排序，不预取全目录。 */
export function usePagedJobs(pageSize: number) {
  const jobs = ref<Job[]>([])
  const total = ref(0)
  const page = ref(1)
  const keyword = ref('')
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref('')
  let disposed = false, request = 0
  let displayedQuery = ''
  let searchTimer: ReturnType<typeof setTimeout> | undefined

  function cancelSearch() {
    if (searchTimer !== undefined) clearTimeout(searchTimer)
    searchTimer = undefined
  }
  function queryKey() { return JSON.stringify([keyword.value.trim(), page.value]) }
  function invalidate() {
    ++request
    if (displayedQuery !== queryKey()) {
      // 保留总数供分页器维持页码边界；清零会触发组件回跳第一页。
      jobs.value = []; loaded.value = false
    }
    error.value = ''
  }
  async function load() {
    cancelSearch()
    if (disposed) return
    invalidate()
    const version = request, search = keyword.value.trim()
    let targetPage = page.value
    loading.value = true
    try {
      let result = await getJobList({ keyword: search, page: targetPage, page_size: pageSize })
      if (disposed || version !== request) return
      // 删除/更新后页数可能缩小；仅补查一次有效页，避免持续变化时无限请求。
      const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
      if (targetPage > lastPage) {
        targetPage = lastPage
        result = await getJobList({ keyword: search, page: targetPage, page_size: pageSize })
        if (disposed || version !== request) return
        if (targetPage > Math.max(1, Math.ceil(result.total / pageSize))) throw new Error('岗位页数再次变化，请重试。')
      }
      page.value = targetPage
      jobs.value = result.list || []; total.value = result.total; loaded.value = true
      displayedQuery = queryKey()
    } catch {
      if (!disposed && version === request) error.value = loaded.value ? '岗位列表刷新失败，保留上次数据。' : '岗位列表加载失败，请重试。'
    } finally {
      if (!disposed && version === request) loading.value = false
    }
  }
  function changePage(value: number) {
    if (value === page.value || !Number.isInteger(value) || value < 1) return
    page.value = value
    return load()
  }
  function search() {
    page.value = 1
    return load()
  }
  watch(keyword, () => {
    cancelSearch(); page.value = 1; invalidate(); loading.value = true
    searchTimer = setTimeout(() => { searchTimer = undefined; void load() }, 250)
  }, { flush: 'sync' })
  onUnmounted(() => { disposed = true; ++request; cancelSearch() })
  return { jobs, total, page, keyword, loading, loaded, error, load, changePage, search }
}
