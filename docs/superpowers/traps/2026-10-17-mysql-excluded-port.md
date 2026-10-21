# MySQL：3306 落入 Windows 排除端口段

日期：2026-10-17（Asia/Singapore）。用户确认诊断方案后执行。

## 症状

`talentmind-mysql-1` 一直为 Created，容器日志为空。Docker Desktop 日志显示 `listen tcp 0.0.0.0:3306: bind` 被访问权限禁止，MySQL 进程尚未启动。

## 根因

`Get-NetTCPConnection -LocalPort 3306` 未发现监听，但 `netsh interface ipv4/ipv6 show excludedportrange protocol=tcp` 均显示排除段 3259–3358，覆盖 3306。实际 TCP 绑定复核：3306 被禁止，23306 可绑定。未确定具体哪个系统组件分配该排除段，不能归因于数据库损坏或其他 MySQL 进程。

## 修复

1. 原数据库停止时，只读挂载 `talentmind_mysql_data` 冷备至私有目录 `D:\backup\TalentMind-mysql-start-20261017-090847`；校验 gzip、tar 目录（191 条目）及 SHA-256。备份为 459457425 字节，SHA-256 `BB4FF89071C72DB41A7109572E1ADF0A706F99F899B227BA7F7E6D04EBC485B3`，并保留变更前配置。
2. Compose 映射改 `23306:3306`，仅修改宿主机端口；同步本地 `.env`、`.env.example` 和启动/监控脚本，PowerShell 保持 UTF-8 BOM。容器健康检查仍使用内部 3306。
3. `docker compose config --quiet` 通过后，执行 `docker compose up -d --no-deps --pull never mysql`，复用相同镜像和原命名卷。
4. MySQL healthy，后端实际连接 `localhost:23306`，通过 READ ONLY 事务核对八表：JD 2988、signal 1540、skill_dict 285、岗位定义/技能/日志 717/717/275、resume/talent_raw 0，与 10-14 保全记录一致。其他 9 个容器 ID/状态不变。

没有导入、迁移、清理业务数据或运行写库集成测试；没有修改 Windows 网络规则。冷备完成归档完整性校验，未在新实例恢复；表数量核对不证明每行内容均一致。

## 回退

变更前五份配置与容器/卷信息保存在上述私有目录。需要回退时先停止 MySQL，再恢复配置并仅重建 MySQL 容器，继续使用原卷；3306 仍处于排除段时，旧映射仍会启动失败。端口配置回退无需恢复数据卷，冷备不得直接覆盖正在使用的数据库。

## 教训

端口没有监听不等于允许绑定。Created + 空容器日志时，应检查 Docker 宿主机日志及 Windows 排除端口，先定位启动阶段。改宿主机端口须同步应用连接和运维探测，保留容器内部端口；不能通过重导数据库、删除卷或重置 Docker 处理端口权限问题。
