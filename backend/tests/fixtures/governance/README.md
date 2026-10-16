# B2 第二轮合成参考

`synthetic-reference.v1.json` 含 14 条短 JD，预期由 Codex 逐项手写并按原文核对字符位置，独立于提取器输出；**尚未经过人类审核，不是人工真值**。它仅用于读取器、预测投影、差异报告和指标程序自检，不支持真实语料或合成语义准确率结论。`review_status=pending_human_review`、`method=synthetic_test_oracle` 必须保留。

样例覆盖同义词、版本、技能年限/学历/行业/证书、词典外项、公司/福利反例、ANY/ALL、四类技能、否定程度、经验对象、仅提及和待判断。预期并非按当前程序输出抄写：版本句和 Java 年限句的期望语义与旧 B2 的保守 uncertain 有意不同，评测必须呈现差异，不能改写历史以使指标变绿。

后续标注格式：根对象提供 schema_version、dataset_id、corpus_kind、reference（方法、复核状态/人名、合法使用依据、版本、备注）与 samples。每样本显式提供 input_row 和 annotations；skills/non_skills/candidates/groups 四列表均必填，空列表表示审核确认在该维度无事实，缺字段表示缺标注并拒绝读取。技能用 name（具体版本采用 `canonical@version`）、state、显式必填category（null表示待复核并从分类分母排除）、可选 requirement_object/degree 和 evidence。组合单独保存 relation/state/members/member_states/evidence，成员状态不由组状态推导。

字符位置为 Python Unicode 字符的 `[start,end)`，不是字节或 UTF-16 单元。输入身份/正文必须和保存的预测快照一致。程序会拒绝重复 JSON 键、样本 ID、重复参考事实及错误参考引文；预测中的重复事实算额外误提，错误引文作为证据错误报告。

真实样本只有在合法使用依据非空、方法为 human_annotation 或 model_assisted_human_annotation、具名人类逐条审核且 review_status=human_reviewed 后才允许语料评测模式。系统只能核验这些声明是否完整，不能自动核验法律权利或审查者身份；不可填写虚假声明。模型草稿不可直接成为真值。真实样本默认只保存在忽略的本地目录，提交前另行审查许可和隐私。

读取器不自动认可样本规模充分；报告保留样本数、各类分母和未覆盖/未定义指标，无正式质量阈值。
