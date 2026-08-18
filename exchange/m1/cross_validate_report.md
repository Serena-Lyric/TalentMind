# M1 多源交叉验证报告（D42，2026-08-17）

- 数据：linkedin 5000 × hn 1796（均 cleaned）
- 匹配规则：normalize_title + hn 段（≥2 词、≥6 字符）↔ linkedin 双向包含 + 长度比 ≥0.6
- 结果：匹配 371 对；hn 命中率 20.7%
- 命中行：cross_source=1 共 426 行（hn 371 + linkedin 55）
- quality 上浮：MAX(原 quality, 0.85)（多源一致置信下界）

| hn id | linkedin id | hn 标题 | linkedin 标题 |
|---|---|---|---|
| 120207 | 111499 | PrairieLearn (Remote US) — Full-Stack Software Eng | Software Engineer |
| 120213 | 112063 | Ontix | Technical Product Manager | Remote (US) | Product Manager |
| 120218 | 111499 | ThoughtMetric | Senior Software Engineer | Locatio | Software Engineer |
| 120219 | 111555 | Credo Health | Full Stack Engineer | NYC (HYBRID — | Full Stack Engineer |
| 120224 | 111499 | Wildflower Health | Junior Software Engineer | Rem | Software Engineer |
| 120228 | 112803 | DoubleVerify (DV Scibids) | Sr. Data Engineer I |  | Data Engineer |
| 120230 | 112039 | Ecosmic | Senior DevOps Engineer | Remote (Italy)  | DevOps Engineer |
| 120238 | 111499 | Rho | Software Engineer | NYC (Soho) | ONSITE | Fu | Software Engineer |
| 120243 | 112465 | ChainSecurity | Blockchain Security Engineer | Ful | Security Engineer |
| 120244 | 115797 | Vitalize | Full-time Engineer | Remote (US, SF in- | Engineer |
| 120251 | 111658 | Disney | Senior Software Engineer, Backend | ONSIT | Senior Software Engineer |
| 120255 | 111499 | Prolific | Senior Software Engineer | Hybrid ONSID | Software Engineer |
| 120256 | 112465 | Factory | Security Engineer | ONSITE, San Francisc | Security Engineer |
| 120257 | 111675 | Third Iron | Senior Quality Engineer | REMOTE (US) | Quality Engineer |
| 120263 | 115738 | MassChallenge | Chief Technology Officer | Boston, | Chief Technology Officer |
| 120266 | 111499 | Yardstik | Senior Software Engineer | Minneapolis, | Software Engineer |
| 120268 | 111499 | Enveritas (YC S18, non-profit) | Backend Software  | Software Engineer |
| 120271 | 111844 | Forecasting Research Institute (FRI) | Data Engine | Data Engineer/ETL |
| 120272 | 111844 | IPinfo.io | Data Engineer | REMOTE (Anywhere) | Fu | Data Engineer/ETL |
| 120279 | 111658 | Axo Ventures | Senior Software Engineer (Founding  | Senior Software Engineer |
