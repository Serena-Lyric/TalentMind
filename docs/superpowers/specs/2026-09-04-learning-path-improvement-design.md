# 技能学习路径升级设计（针对性改进建议 + 岗位学习路径规划）

- 日期：2026-09-04
- 状态：已获用户确认（方案 A：纯规则、数据驱动，不用 LLM/课程/时长/链接）
- 关联需求：PDF「细粒度人岗差距分析，提供针对性改进建议与岗位学习路径规划」（docs/submit/作品设计实现方案.md 第 21 行）
- 范围：`backend/app/routers/learning.py` 路径生成逻辑 + `frontend/src/components/LearningRoadmap.vue` 展示 + 类型；不改 DDL/数据契约/图谱。

## 一、问题
现状 `generate_learning_path` 把缺口技能按“技能类别”分组，再按组序硬编阶段名（第 1 组=基础补齐、第 2 组=岗位核心…），导致出现“基础补齐 · 其他 / 系统集成、部署运维”等无意义路径；每条技能只有 reason，无任何可执行的针对性建议。

## 二、目标行为
1. 阶段 = 学习优先级（先必备缺口、后加分缺口），阶段内按岗位定义原始顺序（M2 权重序），不再按类别枚举顺序硬编。
2. 每条缺口技能给出“针对性改进建议”，字段全部来自真实数据：
   - category（skill_dict seed / 关键词库，未收录回退“其他”）
   - aliases / display_name（skill_dict seed 别名，帮助理解“学的是什么”）
   - evidence（job_skill.skills[].evidence，JD 原文证据，截断展示）——岗位为何要求该技能
   - bridge_skills（简历已命中且与缺口同类别技能）——个性化衔接点
   - suggestion（以上字段确定性拼装的整句建议；技能词典未收录时如实说明，不编造）
3. 无缺口时返回 at_standard 达标态。
4. 保持“不虚构课程/时长/链接”口径。

## 三、实现要点
- 后端：抽取纯函数 `build_learning_path(...)`（不依赖 DB），证据由 `_evidence_map` 单独按 m2_job_id 查询 job_skill 传入；skill_dict seed 缓存于模块级。
- 响应：保留旧字段，新增字段（suggestion/evidence/bridge_skills/aliases/display_name/overview/at_standard），前端同仓同步。
- 前端：新增“针对性改进建议”面板；学习阶段卡改为语义标题+说明；无缺口显示达标卡；移除“解析完成度无数据时默认 92%”的虚构回退。
- 测试：backend/tests/test_learning_path.py 纯函数单测；前端 `pnpm run build`（vue-tsc）通过。

## 四、明确不做（记为后续项）
- 不引入 LLM 生成文案；不虚构课程、时长、链接。
- 图谱暂无 Skill–Skill 依赖边，本版不做“依赖拓扑/最短路径”排序；如需 PDF 原文的“基于图谱最短路径”，需先补 M3 技能依赖数据（另立任务）。