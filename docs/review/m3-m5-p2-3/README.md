# P2.3 证据来源索引

- 正式业务页面：Vue Hash Router `/graph`；全部图谱输入为同一已核验历史文件。没有独立视觉原型替代交付。
- 最终运行包：`index-6a03b61c.js`。`final-overview.jpg`、`final-python-222.jpg`、`near-final.jpg`、`final-rolled-selected.jpg`及故障夹具图片来自该包；`final-preview.jpg`为恢复IAB正常视口后的490×627画面，其余主要对照为1600×900。
- 原版：`p21-*`来自452c98f独立生产构建；`p22-*`来自原PR33工作树a373427生产预览。没有覆盖P2.1/P2.2原证据，旧66份资产摘要见data-integrity.json。
- 阶段截图：`p23-*`、`azimuth-*`、`pitch-*`、`job-detail.jpg`、`historical-scenario.jpg`、`roll-return.jpg`与`python-last-page.jpg`保留开发/中间构建验证，不能仅凭文件名中的final认定最新包。参数与操作时序见browser-observations.json。
- `python-222-highlights.json`明确标记cff阶段的222次GUI逐边枚举；最终包全部222来源索引、选中身份、边0高亮再次存于browser-final-python.json并独立对原文件核验。
- `performance.json`顶层p21/p22/p23及summary是报告采用结果；Before/Initial分组保留旧包、缓存误用及优化前的负结果，不混入最终统计。完整相机/裁剪/预算差异见主报告。
- `browser-observations.json`保留早期过渡中采样与后续稳定单次往返复测。不得只截取一次未结束动画的strict-equality false，或把最终通过倒写为早期就通过。
- 测试日志统一UTF-8并规范行尾空格供Git diff检查；完整pytest原stdout为已确认的本机GBK，按该编码转码，原stdout留本任务忽略目录。无真实密钥、简历、Cookie、数据库卷或私有原始JD。日志中的offline环境为占位连接。

入口：[阶段报告](../M3-M5-P2-3.md)、[真实前后对照](comparison.html)、[性能汇总](performance-summary.json)、[数据守恒](data-integrity.json)、[代码自检](code-self-review.md)。
