# M3-P2.1 只读布局候选

`p2-1-layout.json` 消费上一层唯一 `graph.json`（7845/11412），绑定 LF SHA-256，并保存输入字节摘要。保留全部原始身份；不是正式目录、事实修复或可导入生产图的替代文件。

算法源码来自 PR #32 `377e9b8`，本轮原 ID 运行采用 Jaccard≥0.10、Leiden/resolution1/seed42/weighted generalized modularity。岗位相似边驱动社区内部加权布局；共享技能使用全部相邻岗位，无相似边孤点不分配社区。参数、源码/生成器摘要、软件版本、分区摘要在文件头/尾可查。坐标是展示布局，不证明职业或业务语义。

复现使用 #32 的独立环境（networkx3.6.1、igraph1.0.0、leidenalg0.11.0；不加入生产requirements、不需要GDS），在backend目录执行：

```powershell
python -m app.graph.candidate_layout --snapshot ../exchange/m3/graph.json --output ../exchange/m3/overlays/new-candidate.json
```

输出必须是本目录内的新文件，拒绝覆盖既有文件。比较后由审阅者决定是否替换候选，不能覆盖上层graph.json或自动导入数据库。正式前端构建时固定所使用候选文件的摘要；历史原件不变时，旧Canvas回退不依赖本候选文件。
