# AGENTS.md — TalentMind AI Agent 行为准则

language: 简体中文

## 脚本编码规则

### PowerShell (.ps1)
- 注释: `#` 单行，`<# ... #>` 块注释
- 编码: **UTF-8 with BOM**（无 BOM 则中文 Windows 上乱码）
- 函数文档写在函数上方用 `#`，**不要放在函数体内**
- `"""..."""` 是字符串字面量，不是注释，会污染函数输出流
- 端口检测用 `Get-NetTCPConnection -LocalPort <port>`，不用文本解析

### Windows Batch (.bat / .cmd)
- **只含 ASCII 字符**，禁止中文、Unicode 框线、emoji
- 只做最少引导（管理员检查 + 调起 pwsh），所有业务逻辑放 .ps1
- 顶部加 `chcp 65001 >nul`

## 文件操作规范

### Edit 工具
- `old_string` 必须在当前文件中唯一且逐字符匹配（含缩进和空行）
- 修改大段代码时，先 Read 确认文件内容，再构造 old_string

### Write 工具
- 写 .bat / .cmd 后确认不含非 ASCII 字符
- 写 .ps1 后用 PowerShell 转存为 UTF-8 BOM:
  ```powershell
  $path = "..."; $content = [System.IO.File]::ReadAllText($path)
  $utf8Bom = New-Object System.Text.UTF8Encoding $true
  [System.IO.File]::WriteAllText($path, $content, $utf8Bom)
  ```

## 平台 API 优先级 (Windows)

| 场景 | 优先 | 禁止 |
|------|------|------|
| 端口检测 | `Get-NetTCPConnection` | `netstat -ano \| findstr` |
| 进程操作 | `Get-Process`, `Stop-Process` | `tasklist` / `taskkill` 文本解析 |
| 文件编码 | `[System.IO.File]::ReadAllBytes` 检查 BOM | 文本启发式猜测 |

## 行为准则

### 不臆测
从其他语言类推语法是 bug 的首要来源。
- 明确陈述假设，不确定就问
- 存在多种解释时列出选项而非悄悄选一个
- 遇到不清楚的地方停下来指出困惑点
- 实例：PowerShell 注释是 `#` 不是 `"""`；cmd.exe 默认 GBK 不是 UTF-8

### 简洁优先（ponytail 7 级决策阶梯）
在写任何代码前，按顺序判断：
1. **YAGNI** — 这东西需要存在吗？不需要就跳过
2. **复用** — 代码库里已经有了就别重写
3. **标准库** — 标准库能做就别自己写
4. **原生平台** — 平台有 API（如 `Get-NetTCPConnection`）就别文本解析
5. **已装依赖** — 能复用已安装的依赖就别引入新的
6. **一行** — 能一行解决就别建函数
7. **以上都不行** → 才写最小能工作的代码

安全底线不偷懒：信任边界的输入验证、防数据丢失的错误处理、用户明确要求的功能。

### 精准修改
- 不要"改进"相邻的代码、注释或格式
- 不要重构没坏的东西
- 匹配现有代码风格，即使你更想用另一种写法
- diff 中每一行都应能追溯到用户请求
- 你留下的孤儿代码（无用 import/变量/函数）自己清理
- 发现无关问题 → 指出但不擅自修改

### 闭环追踪
- 用户提出跨多轮的全局需求时，确认所有子项处理完毕再切换方向
- 每次回复前检查是否有用户已确认但未执行的协议
- 大方向切换前，显式确认上一个需求的未完成子项

### 测试数据清理（强制，D37）
- 测试写入数据库/文件的数据必须在测试后自动清理：按测试夹具特征（job_title / identity_hint / 唯一标记）精确删除，**禁止按 source 等宽泛条件 DELETE**（曾因 `DELETE WHERE source='dataset'` 误删 jd_pool 5000 条，见 `docs/superpowers/traps/2026-08-16-integration-test-wiped-jd-pool.md`）。
- 清理必须放在 `finally` 或 fixture teardown 中，断言失败也不得残留。
- 运行集成测试后，agent 必须查询数据库验证测试产出数据已真实清理（夹具行计数为 0）且生产数据未被误删，并把核查结果写入回复。

### 工作前状态同步（强制）
- 开始任何任务前，**先读根目录 `AGENT_START_HERE.md`（通用了解路线）并按路线顺序阅读全部必读文件**（第一条回复须逐文件给出要点证明）；A 角色（M1/集成）任务另读 `A_AGENT_HANDOVER.md`。核心必读：`docs/superpowers/资产与状态.md` + `决策跟踪.md` + `backend/app/contracts/ddl.sql`，确认当前资产位置、契约与未决事项后再动手。
- 新增、移动、删除、迁移资产，修改契约 / 目录 / 交接文件后，必须**及时更新** `docs/superpowers/资产与状态.md`；涉及决策时同步更新 `决策跟踪.md`。
- 未入库模块（`input/人岗匹配/`、`input/jd-filter-package/`、`input/图谱模块/`、`input/岗位能力图谱-前端源码/`，原根目录交付物已统一归档 `input/`）的迁移 / 清理，先确认未决项状态；未裁决前不擅自动作，禁止 `git add -A`（`input/` 内含 421MB 数据与真实简历，已整目录 gitignore 保护）。
- 处理已知限制前先查证 `docs/superpowers/资产与状态.md` 中的记录，不臆测、不重复踩坑。

## 陷阱记录

AI 修复 bug 后，必须在 `docs/superpowers/traps/` 创建记录文件。
命名: `YYYY-MM-DD-<简短描述>.md`。
内容: 症状 → 根因 → 修复 → 教训。

已有陷阱:
- 2026-08-14 job_change_log 导入字段与 DDL/M2 语义不一致（`docs/superpowers/traps/2026-08-14-import-change-log-mismatch.md`）
- 2026-08-16 集成测试误删 jd_pool（`docs/superpowers/traps/2026-08-16-integration-test-wiped-jd-pool.md`）
- 2026-08-16 cleaner experience 单行描述捕获整段致 1406（`docs/superpowers/traps/2026-08-16-cleaner-experience-overlength.md`）
- 2026-08-20 Edge CDP 动态端口与过期 DevToolsActivePort（`docs/superpowers/traps/2026-08-20-edge-cdp-active-port-stale.md`）
- 2026-08-20 Edge CDP 端口落入 Windows 排除段（`docs/superpowers/traps/2026-08-20-edge-cdp-port-excluded.md`）
- 2026-08-20 BOSS 详情字段合并后丢失（`docs/superpowers/traps/2026-08-20-boss-detail-fields-dropped.md`）
- 2026-08-20 BOSS 中文职责标题未抽取（`docs/superpowers/traps/2026-08-20-boss-duties-not-extracted.md`）

## 项目决策要点（2026-08-03）

与 CLAUDE.md 同源，权威清单与最新状态见 `docs/superpowers/决策跟踪.md`，详细设计见 `docs/superpowers/specs/2026-08-03-team-plan-design.md` 和 `docs/superpowers/specs/2026-08-11-repository-organization-design.md`。核心：5 机协作、文件交接 + A 唯一集成、技术栈自选；数据契约冻结于 `backend/app/contracts/ddl.sql`（加表/加字段自由，改/删字段须全队通知）；岗位定义不含 status，source 仅记录来源平台。

仓库边界：`TalentMind` 同时是 A 的 M1 数据采集开发仓和 M1–M5 完整系统唯一主仓。正式后端源码只放 `backend/app/`，前端只放 `frontend/`；`exchange/` 只存交接文件、接口自述和小型 Mock；大型本地数据放 Git 忽略的 `data/local/`。旧 `backend` 不整体删除，重复代码只有在迁移、测试和集成验证通过后才清理，Git 历史负责追溯。

当前例外：`input/人岗匹配/` 的 M4 原型迁移暂缓（原根目录交付目录已归档 `input/`，2026-08-16 确认），未经用户再次确认不得移动或删除其中内容。

完整资产清单与已知限制（按轻重分类）见 `docs/superpowers/资产与状态.md`，**工作前必读**。


## 维护约定

1. 发现新陷阱 → 新建 `docs/superpowers/traps/<日期>-<描述>.md` → 更新上方"已有陷阱"索引
2. 修改项目约束 → 同步更新 CLAUDE.md 对应章节
3. 遇到编码/平台/脚本不确定 → 先查阅本文件和 `docs/superpowers/traps/`
4. 资产 / 目录 / 交接文件变更 → 及时更新 `docs/superpowers/资产与状态.md`，并同步 README / CLAUDE.md 相关章节
