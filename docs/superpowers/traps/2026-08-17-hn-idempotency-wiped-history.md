# 陷阱：HN 采集"当日先清后写"误删历史月份岗位（2026-08-17）

## 症状
- 用 `--months 5` 抓入 hn 历史 6 个月 1795 条后，再跑 `fetch_all`（hn 默认只抓当月）→ hn 从 1795 掉到 239（只剩当月帖），历史 6 帖被删。

## 根因
- `fetch_hn_jobs.py` 幂等策略为"当日同 source 先清后写"：`DELETE FROM jd_pool WHERE source='hn' AND DATE(crawled_at)=today`。
- 历史帖与当月帖的 `crawled_at` 都是"抓取当天"，同一天重跑 fetch_all（范围仅当月）会**把历史帖也删掉**，只重抓当月——清空粒度（按天）与抓取范围（按帖/月份）不匹配。

## 修复
- 幂等改为**按帖清理**：遍历本次抓取的 posts，`DELETE FROM jd_pool WHERE source='hn' AND source_detail=:u`（精确匹配 `item?id=<objectID>`），保留未抓取的历史帖。
- 验证：fetch_all（只当月）后 hn 保持 1795/6 帖，当月帖刷新、历史帖保留。

## 教训
- "先清后写"的幂等粒度必须与"本次抓取范围"一致：按天清理只适用于"每天抓同一批"的固定集合；对"增量累积 + 可选历史范围"的数据，应按**唯一键（source_detail/帖 ID）**精确清理。
- 抓取范围可变化（--months）时，清空条件绝不能是宽松的"日期"或"source"；D37 的"禁止宽泛 DELETE"同样适用于幂等清理。