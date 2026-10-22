const token = document.querySelector('#token')
const session = document.querySelector('#session')
const status = document.querySelector('#status')
const buttons = [...document.querySelectorAll('button')]

chrome.storage.local.get(['token', 'sessionId']).then(value => {
  token.value = value.token || ''
  session.value = value.sessionId || ''
})

for (const input of [token, session]) {
  input.addEventListener('change', () => {
    chrome.storage.local.set({
      token: token.value.trim(),
      sessionId: session.value.trim(),
    })
  })
}

async function send(type) {
  await chrome.storage.local.set({
    token: token.value.trim(),
    sessionId: session.value.trim(),
  })
  buttons.forEach(button => { button.disabled = true })
  status.textContent = '正在读取当前页面…'
  try {
    const response = await chrome.runtime.sendMessage({ type })
    if (!response?.ok) throw new Error(response?.error || '采集失败')
    const result = response.data?.result || {}
    status.textContent = JSON.stringify({
      outcome: result.outcome,
      jd_pool_id: result.jd_pool_id,
      reason: result.reason,
      duplicate: response.data?.duplicate,
    }, null, 2)
  } catch (error) {
    status.textContent = String(error?.message || error)
  } finally {
    buttons.forEach(button => { button.disabled = false })
  }
}

document.querySelector('#capture-list').addEventListener('click', () => send('capture-list'))
document.querySelector('#capture-detail').addEventListener('click', () => send('capture-detail'))
