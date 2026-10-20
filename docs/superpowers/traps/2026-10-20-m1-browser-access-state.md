# M1 浏览器准备与访问门禁混淆

日期：2026-10-20。源码/离线测试与仅浏览器烟测，不采集、不写生产库。

## 症状

直接 CLI 在没有 CDP 时失败；控制台 prepare(auto_start=True) 会启动采集。没有目标站点时 CDP 退回其他页面；检测异常返回“无需登录”，把未知当成功。真实 Edge 复用还因 renderer 继承调试参数、逐进程查询监听而超时。

## 根因

启动实现只在 control，状态只用登录 boolean；目标域做子串匹配且缺失有 fallback。动态端口文件没有活跃进程/listener 归属证明。仅检查首个同域页，不能识别登录后的新标签。把整页“安全验证/服务异常”匹配为门禁，既误伤 JD 正文，也漏掉 iframe 门禁；BOSS 状态选择器少于提取器集合。

## 修复

统一 browser.py 准备/状态服务；prepare 绝不启动采集，CLI prepare-only 不导入数据库。独立 Edge 用动态回环端口，只核实主进程并一次读取监听表；受控采集锁定已核验 endpoint/target_id，不再二次 profile fallback，发现的 WS 必须同地址和端口。域名按主机边界匹配，不存在就失败。

用可见正文/卡片的正面证据判断公开可访问，认证证据另计；登录等待只恢复准备，验证码立即返回。显式提示/门禁容器与可见 iframe 优先，未知页面拒绝采集；正文中提到验证/错误处理不等于门禁。共用 BOSS 选择器，补猎聘当前 camelCase 卡片；游客截断单列 content_limited。

## 教训与证据

absence of login 不等于 authenticated；public_accessible 不等于完整详情。CDP 可达不等于浏览器归属正确，profile 文件不等于仍活跃。控制台准备与任务启动不能共享隐式副作用。

模拟测试与 JavaScript 合成 DOM 回归覆盖首次/重复启动、动态/过期端口、错误主机、跨端口WS、门禁覆盖、正文误判、登录/超时恢复、多标签与prepare-only无采集。真实烟测仅证实独立Edge回环监听、BOSS验证阻断、猎聘公开搜索/单详情、智联公开但游客受限；没有处理验证、自动登录或写库。完整结果与待审限制见 [阶段报告](../../review/M1-browser-runtime.md)。
