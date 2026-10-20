# CLAUDE.md — Claude 补充入口

本仓库通用工作规则统一维护于 [AGENTS.md](AGENTS.md)，开始按 [AGENT_START_HERE.md](AGENT_START_HERE.md) 选择阅读范围；本文件不复制产品决策、历史基线或安全清单。

- Claude 同样遵守 AGENTS 的私有文件、未提交修改、隔离测试、契约及高风险操作许可规则；工具自动批准不等于用户授权迁移或删除真实数据。
- 产品讨论与审查以 [当前产品决策](docs/PRODUCT_DECISIONS.md) 为入口；发现未决或冲突应向用户说明，不能用模型建议填成已确认规则。是否已实现须核对实际代码与测试。
- 作为 ChatGPT 审查流程的协作者时，按 [AGENTS 的 GitHub 流程](AGENTS.md#3-github-协作流程)提供定向修改或证据，不把自身自检写成 ChatGPT 已复审通过，也不代替用户授权合并。

模块状态见 [资产与状态](docs/superpowers/资产与状态.md)，历史裁决见 [决策跟踪](docs/superpowers/决策跟踪.md)；无需在这里重复维护摘要。

- M1 prepare 只准备浏览器，不能触发采集；公开可访问与认证、完整详情分开判断，遇人工验证停止。见[浏览器访问陷阱](docs/superpowers/traps/2026-10-20-m1-browser-access-state.md)。
- CN详情失败、游客截断或身份未核实不能用列表技能补成完整JD；正文换行及目标容器须保留。见[详情门禁陷阱](docs/superpowers/traps/2026-10-20-cn-detail-gate.md)。
- M1控制器须向原循环传递解析后的配置及UTF-8约定；离线子进程通过不等于Gate1或站点验证解除。见[历史控制链路陷阱](docs/superpowers/traps/2026-10-20-m1-controller-loop-compat.md)。

- 真实图谱来源校验须同时绑定 JD/陈述/技能身份，Python 原文偏移按 Unicode 码点处理；不要以文件 hash 代替关联校验。见[真实链路陷阱](docs/superpowers/traps/2026-10-20-real-graph-source-binding.md)。

- 真实JD结构分割不能切断共享否定、组合或整体加分范围；标注摘录须保留目标与上下文，未签审不作真值。见[结构与作用域陷阱](docs/superpowers/traps/2026-10-20-real-jd-structure-and-scope.md)。

- P2.5维护：主体类型由知识身份决定；密度只影响视觉占用，不改布局、可见性或拾取；关系颜色与事实类型分离。见[视觉陷阱](docs/superpowers/traps/2026-10-19-knowledge-body-density-and-gradient.md)，验收证据见[P2.5报告](docs/review/M3-M5-P2-5.md)。

- P2.3相机维护补充：控制器`stop()`不等于原位中断，须同步当前/结束状态并处理最后吸附帧；见[相机陷阱](docs/superpowers/traps/2026-10-19-galaxy-camera-transition.md)。产品原则仍按主文档§8，实现与验收证据集中在[P2.3报告](docs/review/M3-M5-P2-3.md)，不在此复制状态清单。
