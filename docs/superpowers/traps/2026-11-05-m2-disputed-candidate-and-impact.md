# M2 争议候选状态与投影影响兜底

日期：2026-11-05。范围：Issue #61 / PR #62 第三轮修复；离线候选知识链路。

## 症状

- 单个 corroborated 候选被标为 disputed 后，重新 projection/align 仍得到 exact_synonym，
  画像也会继承这一确定映射；普通第三份 JD 观察又把 disputed 自动改回 corroborated。
- 静态知识不变、projection 只变 policy/revision 时，影响报告虽记录 SHA 变化，
  却返回空 affected 且 conservative=false；同时发生已知别名变化时也会漏掉兜底。

## 根因

- 读取端用候选数量代替候选可用状态；观察入口只保护 withdrawn，与 revise 的保护不一致。
- 新观察重新写入证据分类原因，覆盖了原来的争议/撤回原因。
- 影响范围由概念列表差异驱动，没有独立比较 projection 策略和元数据；
  单纯在“没有任何语义差异”时回退，又会被同批的局部已知变更掩盖。

## 修复

- 保留争议 projection 和 registry 历史；单个 disputed 返回 unknown，保留 candidate ID、
  candidate version SHA 和明确理由，不伪造单元素 ambiguous、不选择 concept。
- observe 在 disputed/withdrawn 下只追加证据和证据质量，保留状态、原因、描述与竞争假设。
  不新增身份裁决或恢复流程；解除争议仍需后续有依据的明确机制。
- 独立比较 projection 除 concepts 外的元数据；变化时保守重评全部传入记录，
  即使伴随可定位的静态或候选概念变化。无变化不触发；原有精确增删修订定位继续保留。
- 合成回归贯通 registry→projection→alignment→profile，并持久化重读旧对齐与投影。
  本地完整受影响回归为 208 passed；固定提交的 CI 证据在 Issue #61，不据此宣称市场准确率。

## 教训

候选存在、证据丰富和状态允许使用是不同条件。争议不会因来源数量增长自行解决；
安全状态与原因必须跨写入、投影和下游消费维持一致。版本变化的未知影响要单独兜底，
不能因为同批某一项可解释就认定整批可精确定位。
