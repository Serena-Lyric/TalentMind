import { captureCurrentPage } from './extractor.js'

const API = 'http://127.0.0.1:18000'

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
  if (!extracted?.ok) throw new Error(extracted?.reason || '页面内容无法提取')
  const response = await fetch(`${API}/api/collection/bridge/sessions/${encodeURIComponent(pairing.sessionId)}/captures`, {
    method: 'POST',
    credentials: 'omit',
    headers: {
      'Content-Type': 'application/json',
      'X-TalentMind-Bridge-Token': pairing.token,
    },
    body: JSON.stringify(extracted.capture),
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok || payload.code !== 0) {
    throw new Error(payload.message || payload.detail || `桥接请求失败：HTTP ${response.status}`)
  }
  return payload.data
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!['capture-list', 'capture-detail'].includes(message?.type)) return false
  capture(message.type === 'capture-list' ? 'list' : 'detail')
    .then(data => sendResponse({ ok: true, data }))
    .catch(error => sendResponse({ ok: false, error: String(error?.message || error) }))
  return true
})
