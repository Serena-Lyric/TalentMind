# M1 控制器与旧循环接入缺口

日期：2026-10-20。本轮用户选择先离线修复，未进行真实采集。

## 症状

原CN循环支持自定义搜索模板，但controller配置更新/启动未转发；父进程只经Settings读.env时，子进程缺配置；Windows子进程日志默认编码与watcher UTF-8不一致，质量计数可能缺失。新质量口径/stop_reason仅留在payload未进入任务历史。单轮业务异常被循环捕获后仍exit0；BOSS详情分支可吞传输关闭并继续下一条。

## 根因

新旧接口接入不完整，不是采集核心不存在。Settings读取文件不等于导出os.environ；Python stdout不一定默认UTF-8。WebSocketException未统一为CdpError，普通页面错误与连接失效混用。历史循环仍调用同一run_fetch，不能认为换入口即可解除网站验证。

## 修复

原controller转发模板、传递已解析Settings并固定UTF-8；解析新质量计数和停止原因、未知历史质量不伪造；单轮异常返回失败，watcher不覆盖明确error。统一CdpConnectionError供原循环停止，BOSS传输中断重抛，保留既有已提交good与普通单条页面容错。未修改站点身份/请求策略或恢复持续任务。

## 教训与验证

真实子进程离线回归从control.start_task→原CN --once→原fetch/pipeline→临时SQLite→watcher/history，证明模块接入；不是Gate1真实来源/写库成功。新回归不依赖私有runner，普通pytest15项通过；M1定向263通过，全量残留10项历史/环境失败。详细差异、状态和准入见[历史链路报告](../../review/M1-historical-chain.md)。用户确认验证尚未处理，真实阶段未执行，不使用历史模板或重开浏览器去探测。
