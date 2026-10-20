# M1 浏览器准备与访问状态实施计划

> 执行：在现有 #40 工作树内连续实施，使用 executing-plans、TDD，最终独立代码审查；本轮用户的八项要求为已确认规格，不再增加审批环节。

**目标：** 控制台、单次 CLI 与循环入口共用独立 Edge 的准备/连接/页面状态能力，准备操作无数据库或采集副作用。

**架构：** 复用 CdpClient、现有站点 DOM 选择器和 Edge 启动参数，抽取 `collect/browser.py`。CDP 层严格匹配真实域名、拒绝非回环端点；运行时核实 Edge 的独立 profile 与调试端口，不接管其他浏览器。页面状态采用可见 DOM 正面证据，不以没有登录文案判为认证成功。

**技术：** Python 标准库、已有 httpx/websockets；Windows 原生进程查询。不新增依赖，不修改前端、M2/M3、DDL 或配置。

## 约束与接口

- `prepare(platform, endpoint, user_data_dir, timeout, wait_for_login, url=None)`：可启动 Edge、创建目标域页面并轮询；只返回状态，绝不调用数据库或采集任务。验证码与访问限制立即返回，不自动重试绕过。
- `inspect_page(client, platform)`：返回 access_state、can_collect、authentication、reason、内容证据计数；仅已认证内容、公开内容或明确空结果可准备完成。
- `connect_first_page`：按主机或合法子域匹配，目标不存在就抛错；HTTP 与 browser WebSocket 路径一致。
- API 保留旧 reachable/platform_pages/platform_login_required 等字段，增加 platform_access。旧 `auto_start` 参数保留但不再触发任务；显式 `/start` 才有采集副作用。
- CLI 新增 `--prepare-only`、`--browser-timeout`、`--login-timeout`；先准备再进入原 run_fetch。循环通过同一 run_fetch 准备；准备失败不得导入数据库连接层。

## 审查重点

域名伪装和无关 CDP；旧动态端口文件；重复准备创建多个浏览器；卡片仍在但验证弹窗覆盖；手动登录恢复后准备操作误启任务。

## Task 1：CDP 信任边界与浏览器生命周期

- [x] 为 HTTP/WS 目标缺失、恶意主机、远程端点、首次/重复启动、动态端口及过期文件编写失败测试。
- [x] 最小修改 `fetchers/cdp.py`，抽取 `browser.py`；核实独立 Edge profile/端口，动态启动仅监听 127.0.0.1，复用会话只新增缺失平台标签。
- [x] 运行 `tests/test_cdp.py tests/test_browser_runtime.py`，记录 RED/GREEN。

## Task 2：页面状态及控制台/CLI 接入

- [x] 为加载、公开/认证、登录等待与恢复、验证覆盖、空结果、未知错误、超时重入，以及 prepare(auto_start=True) 不采集编写失败测试。
- [x] 复用三平台选择器，状态只依据可见元素；控制台 prepare/status/start 与 CLI 使用共享服务。采集时每次导航后检查验证/错误，不改清洗与持久化。
- [x] 更新受行为变化影响的旧合成 fixture；运行全部 M1 定向测试与阻网非集成测试。只用临时 SQLite，自动清理；不连接真实 DB/平台。

## Task 3：真实只读烟测与交付

- [x] 离线测试通过后只运行 prepare-only；记录三平台匿名/登录/验证状态及独立 Edge 实际监听地址，私有页面证据只放 data/local。
- [x] 对公开可访问搜索，最多打开一个当前页面可见详情检查访问状态；验证码立即停止该平台，不采集/保存 JD 入库。
- [x] 补陷阱、模块文档、前端字段说明、资产状态及阶段报告；说明未能验证的认证/详情路径。
- [x] 独立审查并修复有证据的问题；明确文件暂存提交并推送原 #40，禁止新 PR/合并/真实写库采集。

回退：回退本轮源码提交即可恢复旧实现；仅关闭本轮独立 Edge，不触碰日常 Edge 或删 profile。无数据库变更，无数据库回退。
