import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { captureCurrentPage } from '../bridge-extension/extractor.js'

class FakeNode {
  innerText: string
  textContent: string
  href = ''
  scrollHeight = 120
  clientHeight = 120
  children: FakeNode[] = []
  selectors = new Map<string, FakeNode | FakeNode[]>()

  constructor(text = '') {
    this.innerText = text
    this.textContent = text
  }

  add(selector: string, value: FakeNode | FakeNode[]) {
    for (const part of selector.split(',').map(item => item.trim())) this.selectors.set(part, value)
    const values = Array.isArray(value) ? value : [value]
    for (const node of values) node.children.push(this)
    return this
  }

  querySelector(selector: string): FakeNode | null {
    for (const part of selector.split(',').map(value => value.trim())) {
      const value = this.selectors.get(part)
      if (value && !Array.isArray(value)) return value
    }
    return null
  }

  querySelectorAll(selector: string): FakeNode[] {
    for (const part of selector.split(',').map(value => value.trim())) {
      const value = this.selectors.get(part)
      if (Array.isArray(value)) return value
      if (value) return [value]
    }
    return []
  }

  getBoundingClientRect() {
    return { width: 100, height: 100 }
  }
}

function installDocument(root: FakeNode, href: string, bodyText = '正常页面') {
  const body = new FakeNode(bodyText)
  const document = {
    body,
    title: 'BOSS直聘',
    querySelectorAll: (selector: string) => root.querySelectorAll(selector),
    querySelector: (selector: string) => root.querySelector(selector),
  }
  Object.assign(globalThis, {
    document,
    location: { href },
    getComputedStyle: () => ({ display: 'block', visibility: 'visible', overflowY: 'visible', webkitLineClamp: '0' }),
  })
  return body
}

function card(index: number, title = `Java 后端工程师 ${index}`, href = `https://www.zhipin.com/job_detail/job-${index}.html`) {
  const node = new FakeNode(title)
  const anchor = new FakeNode(title)
  anchor.href = href
  anchor.add('__getAttribute', new FakeNode(href))
  ;(anchor as any).getAttribute = () => href
  return node
    .add('.job-name', new FakeNode(title))
    .add('.salary', new FakeNode('20-30K'))
    .add('.job-area', new FakeNode('北京'))
    .add('.company-name', new FakeNode('示例科技'))
    .add('a[href*="/job_detail/"]', anchor)
    .add('.tag', [new FakeNode('Java'), new FakeNode('Spring Boot')])
}

test('captures at most five visible BOSS list cards with stable detail URLs', () => {
  const cards = Array.from({ length: 7 }, (_, index) => card(index))
  const root = new FakeNode().add('.job-card-wrapper, .job-card-box, .job-card, .job-list-box', cards)
  installDocument(root, 'https://www.zhipin.com/web/geek/jobs?query=Java&city=101010100&page=1')

  const result = captureCurrentPage('list')

  assert.equal(result.ok, true)
  assert.equal(result.capture.kind, 'list')
  assert.equal(result.capture.items.length, 5)
  assert.deepEqual(result.capture.items[0], {
    url: 'https://www.zhipin.com/job_detail/job-0.html',
    title: 'Java 后端工程师 0',
    company: '示例科技',
    salary: '20-30K',
    location: '北京',
    tags: ['Java', 'Spring Boot'],
  })
  assert.equal(JSON.stringify(result.capture).includes('<'), false)
})

test('captures one visible BOSS detail with newline-preserving description', () => {
  const root = new FakeNode()
    .add('.job-name', new FakeNode('Java 后端工程师'))
    .add('.company-info .name', new FakeNode('示例科技'))
    .add('.salary', new FakeNode('20-30K'))
    .add('.job-location', new FakeNode('北京'))
    .add('.job-limit .tag:nth-child(1)', new FakeNode('3-5年'))
    .add('.job-limit .tag:nth-child(2)', new FakeNode('本科'))
    .add('.job-sec-text', new FakeNode('负责 Java 服务端开发\n熟悉 Spring Boot 和 MySQL'))
  installDocument(root, 'https://www.zhipin.com/job_detail/job-0.html')

  const result = captureCurrentPage('detail')

  assert.equal(result.ok, true)
  assert.equal(result.capture.kind, 'detail')
  assert.equal(result.capture.items.length, 0)
  assert.equal(result.capture.detail.url, 'https://www.zhipin.com/job_detail/job-0.html')
  assert.match(result.capture.detail.description, /服务端开发\n熟悉/)
  assert.equal(result.capture.detail.description_truncated, false)
})

test('challenge and foreign pages are not serialized as job content', () => {
  installDocument(new FakeNode(), 'https://www.zhipin.com/web/passport/zp/security.html', '请完成安全验证')
  assert.deepEqual(captureCurrentPage('detail'), {
    ok: false,
    reason: 'security_verification',
    page_url: 'https://www.zhipin.com/web/passport/zp/security.html',
  })

  const detail = new FakeNode()
    .add('.job-name', new FakeNode('Java 后端工程师'))
    .add('.job-sec-text', new FakeNode('负责 Java 开发'))
  installDocument(detail, 'https://evil.example/job_detail/job-0.html')
  assert.equal(captureCurrentPage('detail').ok, false)
})

test('scrolled detail is reported as truncated and never becomes a full capture', () => {
  const description = new FakeNode('负责 Java 服务端开发')
  description.scrollHeight = 400
  description.clientHeight = 120
  const root = new FakeNode()
    .add('.job-name', new FakeNode('Java 后端工程师'))
    .add('.job-sec-text', description)
  installDocument(root, 'https://www.zhipin.com/job_detail/job-0.html')

  const result = captureCurrentPage('detail')

  assert.equal(result.ok, true)
  assert.equal(result.capture.detail.description_truncated, true)
})

test('extractor fails closed when no visible cards or detail body exist', () => {
  installDocument(new FakeNode(), 'https://www.zhipin.com/web/geek/jobs?query=Java')
  assert.deepEqual(captureCurrentPage('list'), {
    ok: false,
    reason: 'no_job_cards',
    page_url: 'https://www.zhipin.com/web/geek/jobs?query=Java',
  })

  installDocument(new FakeNode(), 'https://www.zhipin.com/job_detail/job-0.html')
  assert.deepEqual(captureCurrentPage('detail'), {
    ok: false,
    reason: 'detail_not_found',
    page_url: 'https://www.zhipin.com/job_detail/job-0.html',
  })
})

test('manifest has only explicit-click permissions and a narrow loopback host', () => {
  const manifest = JSON.parse(readFileSync(new URL('../bridge-extension/manifest.json', import.meta.url), 'utf8'))

  assert.deepEqual(manifest.permissions.sort(), ['activeTab', 'scripting', 'storage'])
  assert.deepEqual(manifest.host_permissions, ['http://127.0.0.1:18000/*'])
  assert.equal(manifest.background.type, 'module')
  assert.equal(JSON.stringify(manifest).includes('<all_urls>'), false)
  assert.equal(JSON.stringify(manifest).toLowerCase().includes('cookie'), false)
})
