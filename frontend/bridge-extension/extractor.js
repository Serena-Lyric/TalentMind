/**
 * Self-contained page function. Chrome serializes this function for executeScript,
 * so every helper and selector must remain inside its body.
 */
export function captureCurrentPage(kind) {
  const pageUrl = location.href
  const listLimit = 5
  const text = (node) => (node?.innerText || node?.textContent || '').replace(/\s+/g, ' ').trim()
  const bodyText = (node) => (node?.innerText || node?.textContent || '').replace(/\r\n?/g, '\n').trim()
  const visible = (node) => {
    if (!node) return false
    const style = getComputedStyle(node)
    const rect = node.getBoundingClientRect()
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
  }
  const firstNode = (root, selectors, preserve = false) => {
    const read = preserve ? bodyText : text
    for (const selector of selectors) {
      const nodes = root?.querySelectorAll(selector) || []
      for (const node of nodes) {
        if (visible(node) && read(node)) return node
      }
      const node = root?.querySelector(selector)
      if (node && visible(node) && read(node)) return node
    }
    return null
  }
  const first = (root, selectors, preserve = false) => {
    const node = firstNode(root, selectors, preserve)
    return node ? (preserve ? bodyText(node) : text(node)) : ''
  }
  const uniqueText = (root, selectors) => [...new Set(
    selectors.flatMap(selector => [...(root?.querySelectorAll(selector) || [])])
      .filter(visible).map(text).filter(Boolean),
  )].slice(0, 30)

  const titleSelectors = ['.job-name', '.job-title', '.job-card-left .name']
  const challengeMarkers = /请完成(?:安全)?验证|访问异常|行为异常|安全验证/
  const detailBody = firstNode(document, ['.job-sec-text', '.job-detail', '.job-description', '.job-detail-section'], true)
  const challengeUrl = /(?:_security_check=|\/(?:passport|security|captcha)(?:\/|\.|$))/i.test(pageUrl)
  const challengeOverlay = [...document.querySelectorAll('.geetest_panel, .verify-wrap')].some(visible)
    || [...document.querySelectorAll('[role="dialog"]')].some(node => visible(node) && challengeMarkers.test(text(node)))
  if (challengeUrl || challengeOverlay || (!detailBody && challengeMarkers.test((document.body?.innerText || '').slice(0, 3000)))) {
    return { ok: false, reason: 'security_verification', page_url: pageUrl }
  }

  let parsed
  try {
    parsed = new URL(pageUrl)
  } catch {
    return { ok: false, reason: 'unsupported_page', page_url: pageUrl }
  }
  if (parsed.protocol !== 'https:' || !['zhipin.com', 'www.zhipin.com', 'm.zhipin.com'].includes(parsed.hostname)) {
    return { ok: false, reason: 'unsupported_page', page_url: pageUrl }
  }

  if (kind === 'list') {
    if (!parsed.pathname.startsWith('/web/geek/job')) {
      return { ok: false, reason: 'unsupported_page', page_url: pageUrl }
    }
    const cards = [...document.querySelectorAll('.job-card-wrapper, .job-card-box, .job-card, .job-list-box')]
    const seen = new Set()
    const items = []
    for (const card of cards) {
      if (!visible(card) || items.length >= listLimit) continue
      const anchor = card.querySelector('a[href*="/job_detail/"]')
      if (!anchor) continue
      let href = ''
      try {
        href = new URL(anchor.getAttribute?.('href') || anchor.href, pageUrl).href
      } catch {
        continue
      }
      const url = new URL(href)
      if (!['www.zhipin.com', 'zhipin.com', 'm.zhipin.com'].includes(url.hostname)
          || !url.pathname.startsWith('/job_detail/') || seen.has(url.href)) continue
      const title = first(card, titleSelectors)
      if (!title) continue
      seen.add(url.href)
      items.push({
        url: url.href,
        title,
        company: first(card, ['.company-name', '.company-text', '.company-name-text']),
        salary: first(card, ['.salary', '.job-salary']),
        location: first(card, ['.job-area', '.job-location', '.job-card-left .job-area']),
        tags: uniqueText(card, ['.tag-list .tag', '.job-card-left .tag', '.job-limit .tag', '.tag']),
      })
    }
    if (!items.length) return { ok: false, reason: 'no_job_cards', page_url: pageUrl }
    return {
      ok: true,
      capture: {
        schema_version: 'm1-browser-bridge-v1',
        kind: 'list',
        page_url: pageUrl,
        items,
        detail: null,
      },
    }
  }

  if (kind !== 'detail' || !parsed.pathname.startsWith('/job_detail/')) {
    return { ok: false, reason: 'unsupported_page', page_url: pageUrl }
  }
  const title = first(document, titleSelectors)
  const descriptionNode = detailBody
  if (!title || !descriptionNode) {
    return { ok: false, reason: 'detail_not_found', page_url: pageUrl }
  }
  const description = bodyText(descriptionNode)
  const descriptionTruncated = [descriptionNode, ...descriptionNode.querySelectorAll('p,pre,section,article,div')].some(part => {
    const style = getComputedStyle(part)
    return visible(part) && text(part)
      && (['hidden', 'clip'].includes(style.overflowY) || Number(style.webkitLineClamp) > 0)
      && part.scrollHeight > part.clientHeight + 2
  })
  return {
    ok: true,
    capture: {
      schema_version: 'm1-browser-bridge-v1',
      kind: 'detail',
      page_url: pageUrl,
      items: [],
      detail: {
        url: pageUrl,
        title,
        company: first(document, ['.company-info .name', '.company-name', '.info-company .name']),
        salary: first(document, ['.salary', '.job-salary']),
        location: first(document, ['.job-location', '.job-area']),
        experience: first(document, ['.job-limit .tag:nth-child(1)', '.job-limit']),
        degree: first(document, ['.job-limit .tag:nth-child(2)']),
        description,
        company_info: first(document, ['.job-sec.company-info', '.company-info .desc', '.company-info']),
        description_truncated: descriptionTruncated,
        challenge_detected: false,
      },
    },
  }
}
