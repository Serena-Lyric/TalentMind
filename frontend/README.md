# frontend — TalentMind 前端

唯一正式前端：Vue 3、TypeScript、Vite、Element Plus、Pinia、Three.js。产品仍处于本地开发阶段，登录只是演示会话，不代表后端生产鉴权。

## 七个业务页面

| 路由 | 用户操作与实际能力 |
|---|---|
| `/collection` | 准备、显式开始/停止受控采集，查看原文/质量/身份；从原文选择 JD 进入 M2。频率与验证门禁保持。 |
| `/m2` | 选择已有 JD 并冻结，显式执行 delivery，读取事实/证据、五态/组合/条件、知识、技能候选、工作研究及版本历史。 |
| `/jobs` | 浏览共享岗位画像与来源、维护必备/加分要求；画像不冒充招聘职位。 |
| `/evolution` | 查看画像编辑前后值/原因/时间，显式比较两个新 M2 运行；演示及未知历史明确身份。 |
| `/graph` | 浏览历史交接图，或从 M2 进入指定运行的研究图；使用固定快照摘要，读取失败不切换数据集。 |
| `/resume` | 解析 PDF/DOCX/TXT，展示实际技能文本规则分及最多三项推荐。 |
| `/learning` | 显式选择前三推荐或其他合格画像，以同一要求版本生成路径；要求变化提示重算。 |

`/login`、`/resume-demo`（当前简历预览与PDF导出）为辅助流程。看板与分析中心已删除。画像API只保留列表/来源统计/详情/编辑/导出；无页面消费者的新增、删除、批量删除和导入入口已退役。刷新丢失内存简历，退出/切换会话清空简历、推荐、目标和迟到请求的写回资格。

## 运行

Node.js `24.15.0`、pnpm `11.5.1`，在本目录执行：

```powershell
pnpm install --frozen-lockfile
pnpm dev
pnpm test
pnpm run build
```

默认端口18080，`/api`代理到`http://127.0.0.1:18000`；通过`VITE_PROXY_TARGET`覆盖后端，`VITE_API_BASE_URL`覆盖请求基址。`pnpm run typecheck`单独检查类型，build含类型检查。后端与本地访问配置见[根README](../README.md)、[M2交付入口](../backend/app/job_analysis/delivery/README.md)。

## 图谱与来源

默认`/#/graph`读取已核验历史`exchange/m3/graph.json`及布局，历史身份明确；三维星体、相机、Worker和宽线交互保留。来源数据与视觉布局分开，空间距离不代表语义距离。

新版M2点击图谱时URL绑定`m2DeliveryRun`与`m2Graph`，每个artifact请求携带同一`snapshot`摘要。运行进行中也能冻结当前已提交部分结果；停止/恢复后旧快照仍可读。旧M2图只读取已保存bundle，不再通过旧引擎生成。私有离线图预览继续使用`M3_REAL_PREVIEW_DIR`和`?graphDataset=real`，普通构建不复制私有源文件。

错误、未知、未执行与真实零值分开；机器结果与研究候选不成为正式职业或学习目标。岗位分页/搜索使用后端总数；请求倒序、选择切换及卸载不允许旧数据覆盖新选择。历史视觉参数用于已保留的三维对照；旧Canvas旁路已移除。

简历格式、规则分与学习含义见[M4说明](../backend/app/matching/README.md)。实际验证和已知限制集中在[资产与状态](../docs/superpowers/资产与状态.md)。
