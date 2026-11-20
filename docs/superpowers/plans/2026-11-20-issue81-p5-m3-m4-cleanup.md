# Issue #81 P5：M3/M4 旧实现清理计划（2026-11-20）

## 目标与边界

基于 P4 head `4696ee6`，按仓库内 import、FastAPI 路由、前端调用、测试与部署引用整理 M3/M4，删除没有正式消费者的重复图谱构建/展示、旧离线来源图链和旧匹配入口，同时保留线上七页正在使用的 M3/M4 能力：

- `/#/graph` 默认历史图谱：`exchange/m3/graph.json`（7845 节点 / 11412 边）与 `exchange/m3/overlays/p2-1-layout.json` 的校验、展示、搜索、节点定位与直接关系阅读；
- M2 新版 delivery 图谱快照与历史 M2 product 图谱只读读取（`/api/m2/delivery/runs/{id}/graph*`、`/api/m2/runs/{id}/graph*`）；
- 历史运行读取、新旧 delivery 版本比较、工作候选/技能候选维护；
- M4 简历上传、解析、岗位推荐、学习路径：`resume_parser`、`file_parser`、`canonical`、`matcher.quick_match_weighted`、`requirements`、`skill_extractor`、`routers/mvp.py`、`routers/learning.py`；
- `/#/resume`、`/#/resume-demo`（简历预览，由简历页进入）与 `/#/learning`。

不删除 `exchange/m3/graph.json`、`exchange/m3/overlays/p2-1-layout.json`、`data/local`、MySQL/SQLite、持久卷或任何历史运行记录；不启动 Docker、不访问外部模型/招聘站、不触发真实分析；不新建兼容目录，不重命名保留模块。

## 实际消费者映射

以下按仓库内 import、路由注册、前端调用、测试夹具和工作流核对，不按目录名推断。

### M3 后端

| 模块 | 实际消费者 | 处理 |
|---|---|---|
| `app.graph.delivery_bundle` | `routers/m2.py` 的 `/delivery/runs/{id}/graph`、`/graph/{name}`；`frontend/src/graph/deliverySnapshot.ts`；`GraphPanorama.vue` delivery 模式；`test_delivery_graph.py`、`test_m2_graph.py`、`deliverySnapshot.test.ts`、`graphRecovery.test.ts` | 保留 |
| `app.graph.product_bundle` | `routers/m2.py` 的 `/runs/{id}/graph`、`/graph/{name}`；`product_bundle.graph_info` 返回 `graphDataset=real` 历史运行地址；`frontend/src/graph/realSnapshot.ts`、`GraphPanorama.vue` real 模式 | 保留 |
| `app.graph.candidate_layout` | `delivery_bundle.build_layout`、`product_bundle.snapshot_hash`；`test_m3_candidate_layout.py`；前端 layout artifact 校验 | 保留 |
| `app.graph.research.algorithms` | `candidate_layout.py`、`delivery_bundle.py`；current layout 的相似/社区计算 | 保留 |
| `app.graph.diagnose_snapshot` | `backend/app/graph/README.md` 只读诊断命令；`test_m3_snapshot_diagnostic.py`；`rebuild_m2_graph.py` 的禁用提示指向它 | 保留 |
| `app.integration.rebuild_m2_graph.build_graph_data` | `diagnose_snapshot.py` 的独立全量重算对照；`test_m3_graph_integrity.py`、`test_m3_snapshot_diagnostic.py` | 保留；`rebuild()` 仍为禁用入口 |
| `app.integration.import_graph` | `backend/app/integration/README.md`；`test_destructive_guard.py`、`test_integration_mvp.py`；Neo4j 交接导入 | 保留 |
| `app.graph.requirements-offline.txt`（经 `backend/requirements.txt` 的 `-r`） | `candidate_layout.py`、`research/algorithms.py` 的 networkx/igraph/leidenalg | 保留 |
| `app.graph.builder` | 仅 `backend/tests/test_graph.py`；README 明确旧 builder 不能复现当前交接，且禁止默认运行覆盖正式图 | 删除 |
| `app.graph.real_pipeline` | 仅 `test_real_pipeline.py`、`test_real_quality.py`；无路由、脚本、部署或 current delivery/product 消费者；私有预览读取的是已生成的 bundle 文件 | 退役 |
| `app.graph.real_quality` | 仅 `test_real_quality.py`；依赖 `real_pipeline` 与 `governance.evaluation` | 退役 |
| `app.integration.rebuild_chinese_graph` | 无 import、路由、测试、脚本或文档入口；会写 `exchange/m3/graph.json` 并清空 Neo4j | 删除 |
| `exchange/m3/graph.json`、`exchange/m3/overlays/p2-1-layout.json` | 默认 `/#/graph`；`historicalSnapshot.ts`；前端历史/可读性/空间测试；`deploy/tests/test-web-image.sh` 检查构建产物 | 保留 |
| `exchange/m3/mock_job_data.json` | 仅旧 `builder.py` 的测试回退输入 | 删除 |
| `app.job_analysis.screening.*` | 仅 `real_pipeline.py` 与 `test_screening.py`；无路由/前端/脚本消费者 | 随 `real_pipeline` 删除 |
| `app.job_analysis.governance.*` | 仅 `real_pipeline.py`、`real_quality.py` 与 `test_governance.py`、`test_governance_evaluation.py` | 随 `real_pipeline` 删除 |
| `app.job_analysis.semantics.rules/runner/store/validation` | 仅 `real_pipeline.py`、`governance/*` 与 `test_semantics.py`、`test_governance*.py` | 随 `real_pipeline` 删除 |
| `app.job_analysis.semantics.models.Evidence/State` | `baseline/contract.py`、`understanding/core.py`、`knowledge/*`、`work_candidates/*` 等现行链 | 保留 |
| 私有真实图预览（`M3_REAL_PREVIEW_DIR`、`?graphDataset=real` 无 run 参数、`/real-graph-artifacts/*`） | `frontend/vite.config.ts`、`frontend/src/graph/realSnapshot.ts`、`scripts/start-local.ps1 -RealGraphDirectory` | 保留为既有私有 bundle 的只读入口；仓库内生成器 `real_pipeline.py` 退役后不再提供新预览生成，后续确认无使用再评估移除 |

### M4 后端

| 模块/符号 | 实际消费者 | 处理 |
|---|---|---|
| `app.matching.resume_parser` | `routers/mvp.py` 的 `/resume/upload`；`test_resume_preview_parser.py`、`test_resume_learning_repair.py` | 保留 |
| `app.matching.file_parser` | `test_file_parser_reliability.py`；spec §7 明确保留 | 保留 |
| `app.matching.canonical` | `routers/mvp.py`、`routers/learning.py`、`integration/rebuild_chinese_catalog.py`；匹配/学习测试 | 保留 |
| `app.matching.matcher.quick_match_weighted` | `routers/mvp.py` 推荐排序；`routers/learning.py` 路径分数；`test_resume_learning_repair.py`、`test_mvp_reliability.py` | 保留 |
| `app.matching.requirements` | `routers/mvp.py`、`routers/learning.py` 的要求版本绑定 | 保留 |
| `app.matching.skill_extractor` | `resume_parser.py`、`routers/mvp.py`、`routers/learning.py`、`integration/rebuild_chinese_catalog.py` | 保留 |
| `app.matching.matcher.ResumeJobMatcher/match_resume_job/batch_match/quick_match/similarity_score`、模块 `__main__` | 仅 `test_matching.py` 与已退役 CLI；无路由/前端调用 | 删除，收敛为 `SKILL_WEIGHTS` + `quick_match_weighted` |
| `app.matching.job_parser` | 仅旧 matcher 全文匹配与已退役 CLI；`routers/mvp.py` 不解析 JD 文本 | 删除 |
| `app.matching.main` | 旧命令行入口；无路由/脚本/部署调用 | 删除 |
| `app.matching.resume_matcher_app` | 旧交互式命令行入口；无路由/脚本/部署调用 | 删除 |
| `app.matching.generate_test_data` | 仅上述两个已退役 CLI | 删除 |
| `backend/tests/fixtures/matching/` | 无测试读取；为旧 CLI 生成的样例与数据集 | 删除；`file_parser` 测试使用内联合成输入 |
| `routers/learning.py`、`frontend/src/components/LearningRoadmap.vue`、`frontend/src/api/learning.ts` | 现行 `/#/learning`；无第二套学习路径生成器 | 保留 |

### 前端、测试与工作流

| 引用 | 实际消费者 | 处理 |
|---|---|---|
| `GraphPanorama.vue` 的 historical/delivery/real 三种模式 | 默认历史图谱、M2 新图、M2 历史图；三模式均有路由或后端 URL 来源 | 保留 |
| `comparisonView.ts` 与视觉回退查询参数 | `GraphPanorama.vue`；`graphRecovery.test.ts` 校验 P2.1～P2.5 对照链接 | 保留（现行受控对照，不是退役页面） |
| `/#/resume-demo`、`ResumeDemo.vue` | `ResumeDiagnosis.vue` 成功后进入；PDF 预览辅助流程 | 保留 |
| `backend/tests/test_graph.py` | 仅 `app.graph.builder` | 删除 |
| `backend/tests/test_real_pipeline.py`、`test_real_quality.py` | 仅退役的离线来源图链 | 删除 |
| `backend/tests/test_job_analysis/test_screening.py`、`test_semantics.py`、`test_governance.py`、`test_governance_evaluation.py` | 仅退役的 screening/governance/semantics 运行器 | 删除 |
| `backend/tests/fixtures/governance/`、`fixtures/semantics/` | 仅上述被删测试 | 删除 |
| `backend/tests/test_matching.py` 的旧匹配用例 | 仅旧 matcher 全流程 | 更新为保留的 `extract_skills`、`canonical` 与 `quick_match_weighted` 覆盖；`test_resume_learning_repair.py` 继续覆盖加权分 |
| `.github/workflows/m2-p2-knowledge.yml` | 显式运行 `test_governance.py` | 移除该路径与测试项；保留 knowledge/baseline/understanding 现行测试 |
| `backend/app/graph/README.md`、`exchange/m3/README.md`、`backend/app/job_analysis/README.md`、`backend/app/matching/README.md`、`exchange/m4/README.md`、`frontend/README.md` | 说明已退役入口与保留边界 | 更新说明，不改写历史报告 |

## 保留清单

- M3：`exchange/m3/graph.json`、`overlays/p2-1-layout.json`、`delivery_bundle.py`、`product_bundle.py`、`candidate_layout.py`、`research/algorithms.py`、`diagnose_snapshot.py`、`requirements-offline.txt`、`integration/rebuild_m2_graph.py`（只读重算与禁用保护）、`integration/import_graph.py`。
- M3 路由：`/api/m2/delivery/runs/{id}/graph*`、`/api/m2/runs/{id}/graph*`；默认 `/#/graph` 历史图与三模式展示、搜索、关系阅读。
- M2 历史读取、版本比较、候选维护：不在本轮范围。
- M4：`resume_parser.py`、`file_parser.py`、`canonical.py`、`skill_extractor.py`、`requirements.py`、`matcher.py` 的 `SKILL_WEIGHTS`/`quick_match_weighted`、`routers/mvp.py` 简历上传、`routers/learning.py` 与 `LearningRoadmap.vue`。
- `semantics/models.py`、`baseline/contract.py`、`understanding/`、`knowledge/`、`work_candidates/` 等现行 M2 依赖。
- 私有真实图预览读取链路（现有 bundle 只读，不提供新生成器）。
- 辅助简历预览页 `/#/resume-demo`。

## 删除清单

1. `backend/app/graph/builder.py`、`backend/tests/test_graph.py`、`exchange/m3/mock_job_data.json`。
2. `backend/app/graph/real_pipeline.py`、`real_quality.py`、`backend/tests/test_real_pipeline.py`、`test_real_quality.py`。
3. `backend/app/integration/rebuild_chinese_graph.py`。
4. `backend/app/job_analysis/screening/`（`__init__.py`、`__main__.py`、`inputs.py`、`rules.py`、`runner.py`、`store.py`、`software-related.offline.json`）。
5. `backend/app/job_analysis/governance/`（`__init__.py`、`__main__.py`、`candidates.py`、`catalog.py`、`evaluation.py`、`extract.py`、`policy.v1.json`、`runner.py`、`store.py`）。
6. `backend/app/job_analysis/semantics/` 的 `__main__.py`、`rules.py`、`runner.py`、`store.py`、`validation.py`；保留 `__init__.py`、`models.py`。
7. `backend/tests/test_job_analysis/test_screening.py`、`test_semantics.py`、`test_governance.py`、`test_governance_evaluation.py`、`backend/tests/fixtures/governance/`、`backend/tests/fixtures/semantics/`。
8. `backend/app/matching/main.py`、`resume_matcher_app.py`、`generate_test_data.py`、`job_parser.py`；收敛 `matcher.py` 并更新 `test_matching.py`。
9. `backend/tests/fixtures/matching/`（旧 CLI 样例、生成数据与未被测试读取的样本）。
10. 同步更新工作流与 README 说明。

## 明确不删除

- `exchange/m3/graph.json`、`exchange/m3/overlays/p2-1-layout.json`、`data/local`、MySQL/SQLite、Neo4j 卷与历史运行记录。
- `semantics.models`、`baseline`、`knowledge`、`understanding`、`work_candidates`、delivery/product 只读历史。
- M4 简历上传、岗位推荐、学习路径、`resume-demo` 辅助页。
- Git 历史；退役实现只能从历史找回。

## 实施步骤

1. 删除 M3 旧构建/展示分叉：`builder`、`real_pipeline`、`real_quality`、`rebuild_chinese_graph`、`mock_job_data` 及对应测试。
2. 退役 screening/governance/semantics 运行器，保留 `semantics.models`；删除其测试与夹具。
3. 删除 M4 旧 CLI 与 `job_parser`，收敛 `matcher.py`；更新 `test_matching.py`，删除无消费者的 matching 夹具。
4. 更新 `.github/workflows/m2-p2-knowledge.yml` 与相关 README/说明；不重写历史报告与产品决策。
5. 全局 `git grep` 核对无残留 import/符号引用，运行后端与前端验证。

## 验证

- `cd backend && .venv/Scripts/python.exe -m pytest -m "not integration" -q`，输出重定向临时文件只读尾部；记录无关偶发失败。
- `cd frontend && pnpm test && pnpm run typecheck && pnpm run build`。
- `git grep -n "graph.builder\|real_pipeline\|real_quality\|rebuild_chinese_graph\|resume_matcher_app\|generate_test_data\|matching.main\|job_parser\|screening\|governance\.\|semantics\.rules\|semantics\.runner\|semantics\.store\|semantics\.validation"` 确认无残留代码引用（历史文档、`data/local` 与 Git 历史除外）。
- `git diff --stat` 只包含本计划与计划内文件。
- 不启动 Docker、不访问外部模型/招聘站、不触发真实 M3/M4 分析；不修改 `data/local` 或数据库。

## 风险与说明

- 退役 `real_pipeline/real_quality` 会移除离线来源图生成与 governance evaluation 能力；这些从未成为网页第二套正式分析链，原实现留在 Git 历史。线上 M3 历史图与 M2 delivery/product 图读取不受影响。
- 私有真实图预览保留只读链路；仓库内不再提供新 bundle 生成器。若后续确认无既有私有 bundle 使用，可另行移除预览插件与 `start-local.ps1` 参数。
- `rebuild_m2_graph.py` 虽含禁用 `rebuild()`，但 `diagnose_snapshot` 与完整性测试仍使用其纯函数，不能按“重复构建入口”一并删除。
- 删除 `test_screening/test_semantics/test_governance*` 会减少离线研究回归数量；现行 M2 knowledge/delivery 测试与 `semantics.models` 契约测试保留。
- M4 上传路由使用自身文件抽取与 `resume_parser`/`skill_extractor`/`quick_match_weighted`；删除旧 CLI 与 `job_parser` 不改变 `/resume/upload` 与 `/learning/generate-path`。
- 本轮只做离线测试，不声称线上七页已人工复验；M3 新 M2 结果入图与 M4 真实简历准确率仍按 Issue #81 后续功能事项处理。
