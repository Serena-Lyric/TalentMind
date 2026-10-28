# 10月21日晚主仓统一与功能验收

日期：2026-10-21，Asia/Singapore。基线15d5275；继续codex/product-integration-20261020与Draft PR #44，不新建分支/工作树/PR，不合并master。原10项保全整合提交38aa011，功能提交见本报告Git历史。

## 主仓与保全

已在 `D:\Application\ClaudeCode\repository\TalentMind` 普通检出现有集成分支。原主仓为codex/m1-stage-02@e8235c8；原集成工作树干净且无运行服务，先安全detached到15d5275释放分支。未reset、clean、强制检出或删除工作树。

迁移前备份到 `D:\backup\TalentMind-unify-20261021-1930`，逐文件复制并比较SHA：107180文件、1398460884字节，另有已verify的Git bundle及staged/unstaged patch。包含私有配置、SQLite、冻结输入和报告；一个既有验收目录带依赖缓存，成本偏大，本轮未擅自删除。原stash `pre-unify-20261021-main-10-protected`仍保留。

| 原10项修改 | 保护/整合方式 |
|---|---|
| AGENTS.md | 原字节备份；保留新规范，补回端口陷阱入口 |
| CLAUDE.md | 原字节备份；补回MySQL修复说明 |
| README.md | 保留23306说明 |
| backend/.env.example | 目标分支已含同样23306修复，无重复diff |
| docker-compose.yml | 目标分支已含同样23306映射，无重复diff |
| docs/superpowers/决策跟踪.md | 保留新结构并补回D61 |
| docs/superpowers/资产与状态.md | 补回原端口修复与Docker恢复资源收尾记录 |
| scripts/check_collect_status.ps1 | 保留23306修复，BOM/语法通过 |
| scripts/start_system.ps1 | 保留23306修复，BOM/语法通过 |
| 未跟踪2026-10-17-mysql-excluded-port.md | 先备份再完整保留入库 |

主仓.env最终哈希未变。M2等私有目录只复制缺失文件、逐项校验，无同名覆盖；collection/control-state不同，另备份主仓原文件，仅合并历史，current_task/config未变。旧日志绝对路径仍引用保留的原工作树，暂不可删除它。两套SQLite integrity_check=ok，原6份产品报告字节不变。

**前端成员来源仍未取得。** 她在另一台电脑开发；最终fetch及开放PR列表未识别今晚交付分支/PR/SHA，未合入、未将PR #34当作她的成果。本轮前端功能修改基于#44@15d5275。她交付后的一次最终视觉集成尚待完成。

## 启动

主仓根目录执行 `pwsh -NoProfile -File scripts/start-local.ps1` 或双击start_system.bat。实际前端 `http://127.0.0.1:18080/`，M2 `/#/m2`，后端 `http://127.0.0.1:18000/health`。使用页面提供的本地演示账号。stop_system.bat/stop-local.ps1只停本入口进程，保留数据库与Edge。

主仓已补齐锁定前端依赖及已有graph/requirements-offline依赖；后者纳入后端requirements，避免新安装缺包。启动复用既有容器，不导入/迁移/新建数据卷。M2与原文操作仍须显式localhost门禁，演示登录不是生产授权。

## 本机Edge实际验收

| 项目 | 真实结果与边界 |
|---|---|
| M1单轮/准备 | 1关键词/城市/页，5列表/详情上限。显式准备后“未检测到职位内容”/no_access_evidence，启动正确禁用；未绕过网站门禁、未采入新JD，Gate1未通过。 |
| M1批次 | Python/Java×北京/上海=4项，显式保存待执行计划，无run_id、计数为“—”；整批停止后4项取消、started_at为空。未开始真实批量采集。精确验收计划状态已清理，私有证据保留。 |
| M1历史与结果 | 迁移的zhaopin-98c0…可查看5列表、1详情尝试/取得、0完整/入库、1拒绝；结果包含unverified_dom_identity，不补历史正文冒充成功。 |
| M2历史/证据 | 主集120、留出60报告和原文可读；主集113四阶段完成/待审、7输入异常，5885处原文位置、0位置异常。实际查看原文及B1/B2/B2.2/B3标签与未决原因，未重跑120/60分析。 |
| M2新任务 | 真实MySQL冻结5条，run a0a83e542a5f41439f5e0f8f3ea4233c；开始前停止→同run恢复→四阶段5/5、0执行失败/输入异常、全部待审。未重复运行中60条中断实验，沿用此前证据。 |
| M2→M3 | 实际点击主集“生成/查看本次候选图谱”，显示run、v2分析摘要及范围待审99；190节点/1066陈述。搜索python并回溯陈述到JD125137冻结原文成功。 |
| M3空间/回退 | 候选入口使用node-field-v1，星尘/知识层可操作；返回历史图恢复7845/11412。错误manifest摘要时显示0/0及版本错误，没有用其他图冒充。 |
| 其他核心页 | Jobs加载717定义；首页717与旧接口100项列表；能力动态100项选择器；分析页717/Top30技能/14信号天数。简历上传页、学习路径与简历预览真实空态正常。未重新验完整简历匹配算法。 |

一次Vite开发进程在验收中退出，页面显示Network Error；用同一幂等启动入口恢复后，批次保存/停止和后续页面成功。退出根因未确定，不把恢复当成永久修复。

后续安全门禁修复：真实复现确认 BOSS 在搜索页与 `passport/zp/security.html` 之间通过递增 `_security_check` 连续跳转，约6秒后回首页，且浏览器中没有可人工操作的验证页面。TalentMind 没有调用 `Page.reload`；不轮询时没有快速刷新循环，同一 profile 不启用远程调试直接打开页面时等待24秒仍正常。专用浏览器发现17个第三方扩展，但禁用扩展后仍受CDP连接影响。修复后首次启动直接以目标搜索URL打开，默认只检查一次；前端自动刷新不再查询浏览器，状态与准备锁定当前目标标签并明确区分自动安全跳转和人工验证；搜索目标不再生成普通外链。单次CDP连接仍可能被BOSS识别，因此这不保证站内自动化长期可用，后续稳定采集方案见[普通浏览器桥接执行方案](https://github.com/Serena-Lyric/TalentMind/blob/298b94a7b952822ffd9b1201b6c221c85d987424/docs/superpowers/plans/2026-10-21-boss-browser-bridge.md)，问题根因见[陷阱记录](../superpowers/traps/2026-10-21-boss-security-check-loop.md)。

## 运行版本关联

新增graph/product_bundle.py，仅消费指定M2保存报告，复用real_pipeline.project/derive和图谱组件，不调用run_pipeline或重跑分析、不写Neo4j。POST `/api/m2/runs/{run_id}/graph` 显式生成/复用，GET同路径查看；GET `/graph/{manifest,facts,sources,layout,derived}.json`提供受控产物。

生成核验冻结输入、报告摘要、阶段原生报告/版本、namespace/JD ID/指纹与原文位置。manifest绑定产品run、输入SHA、报告SHA、原分析versions、生成代码及产物SHA；浏览器再次校验run/manifest/产物与技能陈述来源。旧图按保存生成版本读取，升级不覆盖或锁死历史。

主集120→113候选观察/7异常，190节点/1066边（1063 uncertain、3 mentioned），范围待复核99；留出60→52/8，143节点/793边（790 uncertain、3 mentioned），范围待复核51。图中“岗位”代表原始JD，非已发布标准职业；全部formal_statistics_eligible=false、未人工审核。B3职业候选仍0，不能把观察图节点当作分类成功。

## 最终验证与数据

- 本轮安全门禁最终相关后端199 passed，完整前端151 passed；类型检查/build通过。既有大chunk及重复动态/静态导入提示保留。后端最终全量为1463 passed / 2 failed / 23 deselected，两项仍为此前已知的B3 canonical来源hash/quote问题。
- 独立审查两项边界均先复现后修复，并定向复审；不替代负责人集中验收。未重复全后端大套件；此前全量中的两项B3来源hash/quote失败仍未解决，未重签或声称全套通过，见[M2报告](https://github.com/Serena-Lyric/TalentMind/blob/36655eef617db1c80f007f4a9bb7423c58c6fc75/docs/review/M2-product-2026-10-21.md)。
- 业务测试仅临时SQLite/文件，finally/teardown清理；精确无执行批次验收文件已不存在，无正式库写入测试或宽泛DELETE。
- 浏览器验收前后MySQL八表全字段有序SHA及计数完全相同：JD2988、signal1540、skill_dict285、定义/技能/日志717/717/275、resume/talent_raw0，无测试数据写入或误删。Neo4j只读查询7845/11412。
- 真实数据、SQLite、截图、日志及完整审计保留于忽略的data/local/unified-acceptance与m2-product，不提交原文或密钥。

## 未完成与23日后

前端成员实际推送来源未交付，最终合入仍待完成；M1正常人工站点访问和有界Gate1仍待通过。B2 uncertain、B3零职业候选、历史正文缺失、旧两项B3测试失败留待质量/来源治理，不补造原文或降门槛。美术、性能/体积、银河细节、旧页100项选择器/文案与开发进程退出根因，不扩展为今晚新轮次。
