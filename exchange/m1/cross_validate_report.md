# M1 多源交叉验证报告（D42，2026-08-17）

- 数据：linkedin 5000 × hn 239（均 cleaned）
- 匹配规则：normalize_title + hn 段（≥2 词、≥6 字符）↔ linkedin 双向包含 + 长度比 ≥0.6
- 结果：匹配 55 对；hn 命中率 23.0%
- 命中行：cross_source=1 共 74 行（hn 55 + linkedin 19）
- quality 上浮：MAX(原 quality, 0.85)（多源一致置信下界）

| hn id | linkedin id | hn 标题 | linkedin 标题 |
|---|---|---|---|
| 116969 | 111555 | Open Education Applications / Neon | Senior/Lead P | Full Stack Engineer |
| 116973 | 113031 | Senzing | Platform Engineer | Remote (USA) | Full- | Principal Platform Engineer |
| 116976 | 111499 | Marple | Software Engineer | Antwerp, Belgium | Fu | Software Engineer |
| 116984 | 116077 | Role: Engineering Manager | Engineering Manager |
| 116986 | 111499 | Software Engineer - Full Stack | New York, NY | Fu | Software Engineer |
| 116995 | 112039 | Aeolus | DevOps Engineer | San Francisco, CA (onsi | DevOps Engineer |
| 116996 | 115797 | Vitalize | Full-time Engineer | San Francisco (hyb | Engineer |
| 116997 | 111499 | Enveritas (YC S18, non-profit) | Backend Software  | Software Engineer |
| 116998 | 111499 | Clad (YC W23) | Software Engineer | NYC | withclad | Software Engineer |
| 117005 | 111499 | MixRank (YC S11) | Software Engineers | 100% Remot | Software Engineer |
| 117019 | 111844 | Well | Data Engineer | Python / SQL / Node.js / Te | Data Engineer/ETL |
| 117024 | 113250 | Apex Dental Partners | Full-Stack Developer | Dall | Fullstack Developer |
| 117046 | 113618 | Flow Traders | Research Engineer | Hong Kong/ Lond | Dev/Research Engineer 2 |
| 117050 | 111499 | Full Stack Software Engineer | San Francisco, CA | | Software Engineer |
| 117052 | 111633 | pganalyze | Marketing Manager | REMOTE (US) | Full | Marketing Manager |
| 117060 | 112063 | Chainguard | Product Manager, Scanner | REMOTE | F | Product Manager |
| 117064 | 112140 | Hestus | Machine Learning Engineer (Python, ML) |  | Machine Learning Engineer |
| 117065 | 114686 | Trustworthy Technology | Earth | Part Time | REMOT | Part Time Cook |
| 117074 | 111658 | Proxima Fusion | Senior Software Engineer (Dev Pla | Senior Software Engineer |
| 117081 | 111499 | Amodo Design (amododesign.com) | Sheffield/London, | Software Engineer |
