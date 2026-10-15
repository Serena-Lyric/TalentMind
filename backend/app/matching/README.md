# matching

M4 简历解析与岗位匹配正式目录（已迁入实现：resume_parser / matcher / skill_extractor / canonical 等，详见 `exchange/m4/README.md`）。`input/人岗匹配/` 原版目录按用户要求暂缓迁移（只读对照，不入库）。

2026-10-15 代码核查：上面的 `exchange/`、`input/` 均相对仓库根目录。正式 API 位于 `backend/app/routers/mvp.py`，PDF/DOCX/文本解析及自动多岗位推荐已接入，上传内容不写 resume 表；旧 `.doc` 的实际二进制兼容性未验证，不能保证所有 Word 格式。

匹配采用加权规则；API 的 `raw_score` 是实际计算分，`display_score` 对低于 90 的候选仍使用 90–100 的随机演示分，不能作为真实准确率。前端学习路径已由 `backend/app/routers/learning.py` 按岗位技能、JD 证据与简历内存态生成确定性缺口和阶段；独立 M4 pathfinder 算法仍未回包。提取/匹配准确率及中文紧邻英文边界仍待专项验证，本轮不改源码。
