# 裸跑 pytest 触发默认全量导入

## 症状

后端使用裸 `pytest -q` 跑完整套件后，正式 MySQL 分析层和 Neo4j 被默认导入入口改写，且测试标记、测试名称和环境变量都不能证明实际写入了哪个目标。

## 根因

`pytest -q` 默认也执行 `@pytest.mark.integration`；旧导入服务默认读取本地回包并整表重建。测试名称中的“幂等”只验证重复结果相等，不能保护当前正式数据，也没有在写入前核对实际连接目标。

## 修复

新增 `backend/tests/conftest.py`：默认给所有 integration item 添加 skip。只有显式设置 `TALENTMIND_ALLOW_INTEGRATION=1`，且人工核对目标是隔离实例后，才允许收集进入。

所有破坏性导入入口另行调用 `destructive_guard.py`：读取实际 MySQL/Neo4j 身份，并要求独立授权文件中的操作、完整目标指纹和有效期同时匹配。测试标记与环境变量不能替代授权文件。

MySQL 指纹必须同时保存 SQLAlchemy 实际宿主 `connection_port` 与服务端 `@@port`（`server_port`）。只保存服务端端口会让同主机不同映射端口下、UUID 相同的克隆库共享授权指纹。

## 教训

“完整测试”不等于“所有标记都执行”。包含真实服务写入的测试必须默认安全关闭；写入授权必须绑定实际目标，不能依赖测试名、文档提醒或运行者记忆。
