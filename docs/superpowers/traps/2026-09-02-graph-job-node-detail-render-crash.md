# 2026-09-02 图谱岗位节点点击后详情栏空白：列表字段以 JSON 字符串返回

## 症状

采集图谱页（/graph）点击“岗位”节点不再显示节点信息；浏览器控制台报错 setup.selectedNode.required_skills.join is not a function，详情栏不出现。技能/行业节点正常。

## 根因

Neo4j 导入层（import_graph.py）把 list/dict 属性统一 json.dumps 成字符串存储，/api/graph/data 读取 Job 节点时把 required_skills / bonus_skills / source 原样返回（JSON 字符串），而前端 GraphNode 类型与详情模板（GraphPanorama.vue）按 string[] 处理并调用 .join('、')，导致岗位节点详情渲染抛错中断。source 因 isinstance(..., list) 判断失败被置空，来源平台也随之丢失。契约（MySQL/回包为数组）与 Neo4j 存储（字符串）不一致。

## 修复

- 后端 backend/app/routers/mvp.py 的 graph_data 在读取侧用 _parse_json_list() 解析 source / required_skills / bonus_skills / scenarios（与已有 _parse_json_object(evolution) 同一模式），兼容“Neo4j 原生 list”与“JSON 字符串”两种存储；不改导入逻辑、不重导数据。
- 重启后端 18000 进程后回归：接口返回数组，platform_label 恢复；浏览器实测点击/搜索选中岗位节点均可显示完整详情（必备技能、加分技能、来源平台等），无渲染报错。

## 教训

- 前端类型声明即契约：只要 API 类型写 string[]，任何一层（存储、序列化、读取）都不允许静默变成 JSON 字符串；跨层字段形状不一致时必须在读取边界归一，并用真实数据做浏览器级验证，不能只看构建通过。
- 详情面板对数组字段调用 .join 前，应保证数据源层已归一，避免渲染期 TypeError 导致整块 UI 不显示。