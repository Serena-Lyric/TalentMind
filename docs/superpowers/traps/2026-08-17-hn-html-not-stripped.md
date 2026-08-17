# 陷阱：HN 岗位评论 HTML 未剥离污染 job_title/raw_text（2026-08-17）

## 症状
- HN "Who is hiring" 评论为 HTML（`<a href=...>`、`<p>` 等）；首次入库后 `jd_pool.job_title` 出现 `<a href="https://...">` 标签，`raw_text` 含 HTML 噪声（M2 提取 evidence 引用时会受影响）。

## 根因
- `fetchers/hn_hiring.py::comments_to_rawjds` 直接把 Algolia items API 返回的 HTML 评论文本作为 RawJD.raw_html / 首行作为 job_title，未剥离 HTML。

## 修复
- `_strip_html()`（BeautifulSoup `get_text("\n")`）在转 RawJD 前剥离 HTML；重抓（`fetch_hn_jobs` 幂等：当日同 source 先清后写）→ 239 条干净数据；验证 `LIKE '%<a %'` 命中 0。

## 教训
- 任何外部文本源进入原始库前，先确认其格式（HTML/纯文本/Markdown）并按契约清洗；job_title 等短字段尤其要防标签污染；fetcher 幂等（当日先清后写）让"修好重抓"零成本。