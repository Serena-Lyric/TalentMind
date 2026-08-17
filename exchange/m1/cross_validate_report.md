# M1 多源交叉验证报告（D42，2026-08-17）

- 数据：linkedin 5000 × hn 1795（均 cleaned）
- 匹配规则：normalize_title + hn 段（≥2 词、≥6 字符）↔ linkedin 双向包含 + 长度比 ≥0.6
- 结果：匹配 371 对；hn 命中率 20.7%
- 命中行：cross_source=1 共 426 行（hn 371 + linkedin 55）
- quality 上浮：MAX(原 quality, 0.85)（多源一致置信下界）

| hn id | linkedin id | hn 标题 | linkedin 标题 |
|---|---|---|---|
| 117692 | 111555 | Open Education Applications / Neon | Senior/Lead P | Full Stack Engineer |
| 117696 | 113031 | Senzing | Platform Engineer | Remote (USA) | Full- | Principal Platform Engineer |
| 117699 | 111499 | Marple | Software Engineer | Antwerp, Belgium | Fu | Software Engineer |
| 117707 | 116077 | Role: Engineering Manager | Engineering Manager |
| 117709 | 111499 | Software Engineer - Full Stack | New York, NY | Fu | Software Engineer |
| 117718 | 112039 | Aeolus | DevOps Engineer | San Francisco, CA (onsi | DevOps Engineer |
| 117719 | 115797 | Vitalize | Full-time Engineer | San Francisco (hyb | Engineer |
| 117720 | 111499 | Enveritas (YC S18, non-profit) | Backend Software  | Software Engineer |
| 117721 | 111499 | Clad (YC W23) | Software Engineer | NYC | withclad | Software Engineer |
| 117728 | 111499 | MixRank (YC S11) | Software Engineers | 100% Remot | Software Engineer |
| 117742 | 111844 | Well | Data Engineer | Python / SQL / Node.js / Te | Data Engineer/ETL |
| 117747 | 113250 | Apex Dental Partners | Full-Stack Developer | Dall | Fullstack Developer |
| 117769 | 113618 | Flow Traders | Research Engineer | Hong Kong/ Lond | Dev/Research Engineer 2 |
| 117773 | 111499 | Full Stack Software Engineer | San Francisco, CA | | Software Engineer |
| 117775 | 111633 | pganalyze | Marketing Manager | REMOTE (US) | Full | Marketing Manager |
| 117783 | 112063 | Chainguard | Product Manager, Scanner | REMOTE | F | Product Manager |
| 117787 | 112140 | Hestus | Machine Learning Engineer (Python, ML) |  | Machine Learning Engineer |
| 117788 | 114686 | Trustworthy Technology | Earth | Part Time | REMOT | Part Time Cook |
| 117797 | 111658 | Proxima Fusion | Senior Software Engineer (Dev Pla | Senior Software Engineer |
| 117804 | 111499 | Amodo Design (amododesign.com) | Sheffield/London, | Software Engineer |
