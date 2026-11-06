import { captureCurrentPage } from './extractor.js'

const API = 'http://127.0.0.1:18000'
const REQUEST_TIMEOUT_MS = 15000
let captureInFlight = false

function storedPairing() {
  return chrome.storage.local.get(['token', 'sessionId'])
}

async function capture(kind) {
  const pairing = await storedPairing()
  if (!pairing.token || !pairing.sessionId) {
    throw new Error('请先在扩展中填写 TalentMind 配对令牌和任务 ID')
  }
  const tab = (await chrome.tabs.query({ active: true, currentWindow: true }))[0]
  if (!tab?.id) throw new Error('没有可读取的活动页面')
  const execution = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: captureCurrentPage,
    args: [kind],
  })
  const extracted = execution[0]?.result
  let captured = extracted?.capture
  if (!extracted?.ok) {
    if (extracted?.reason !== 'security_verification') throw new Error(extracted?.reason || '页面内容无法提取')
    captured = {
      schema_version: 'm1-browser-bridge-v1', kind: 'blocked',
      page_url: extracted.page_url, blocked_reason: 'security_verification',
    }
  }
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const response = await fetch(`${API}/api/collection/bridge/sessions/${encodeURIComponent(pairing.sessionId)}/captures`, {
      method: 'POST',
      credentials: 'omit',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        'X-TalentMind-Bridge-Token': pairing.token,
      },
      body: JSON.stringify(captured),
    })
    const payload = await response.json()
    if (!response.ok || payload.code !== 0) {
      throw new Error(payload.message || payload.detail || `桥接请求失败：HTTP ${response.status}`)
    }
    return payload.data
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error('本地采集服务响应超时，提交结果尚未确认。请先在控制台核对本轮结果，不要直接重复提交。')
    }
    if (error instanceof TypeError || error instanceof SyntaxError) {
      throw new Error('未取得本地采集服务的有效响应，提交结果尚未确认。请检查服务并在控制台核对本轮结果。')
    }
    throw error
  } finally {
    clearTimeout(timeout)
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!['capture-list', 'capture-detail'].includes(message?.type)) return false
  if (captureInFlight) {
    sendResponse({ ok: false, error: '已有采集正在进行，请等待结果后再操作。' })
    return false
  }
  captureInFlight = true
  capture(message.type === 'capture-list' ? 'list' : 'detail')
    .finally(() => { captureInFlight = false })
    .then(data => sendResponse({ ok: true, data }))
    .catch(error => sendResponse({ ok: false, error: String(error?.message || error) }))
  return true
})

