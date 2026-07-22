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

## 陷阱记录

AI 修复 bug 后，必须在 `docs/superpowers/traps/` 创建记录文件。
命名: `YYYY-MM-DD-<简短描述>.md`。
内容: 症状 → 根因 → 修复 → 教训。

已有陷阱:


## 维护约定

1. 发现新陷阱 → 新建 `docs/superpowers/traps/<日期>-<描述>.md` → 更新上方"已有陷阱"索引
2. 修改项目约束 → 同步更新 CLAUDE.md 对应章节
3. 遇到编码/平台/脚本不确定 → 先查阅本文件和 `docs/superpowers/traps/`
