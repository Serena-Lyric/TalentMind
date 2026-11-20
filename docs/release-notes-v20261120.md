# TalentMind v20261120 Release 说明

> 对应 [Issue #81](https://github.com/Serena-Lyric/TalentMind/issues/81)。服务器首次部署使用 `20261118-1` 包完成；本 Release 以最终整合后的代码重新构建公开资产，不复用未合并阶段的包。实际资产名与校验值以发布页为准。

## 版本与来源

- 版本：`v20261120`（示例资产名 `talentmind-code-v20261120.tar.gz`）。
- 来源分支：Issue #81 的 P1–P6 实现，`codex/issue81-p1-deploy`（P1）→ `codex/issue81-p2-m1-linux`（P2）→ `codex/issue81-p6-package`（P6），对应 PR #82/#83/#84；截至 2026-11-20 三个 PR 仍为 Open，发布以最终整合提交为准。
- 运行目标：Ubuntu 24.04 x86_64，Docker Compose，`linux/amd64` 预构建镜像。

## 公开包内容

- 源码与部署目录：`git archive` 生成的代码树，含 `deploy/scripts/`、`deploy/compose.yml`、`deploy/backend/`、`deploy/web/`、`deploy/tests/` 和文档。部署脚本与配置由 `.gitattributes` 固定为 LF，避免 Windows `core.autocrlf=true` 把 CRLF 打入发布包。
- 5 个镜像：`talentmind-backend`、`talentmind-web`、`mysql:8.0`、`neo4j:5-community`、`redis:7-alpine`（Neo4j/Redis 默认不启动）。
- `app/deploy/package.env`：安装脚本据此选择镜像版本。
- `SHA256SUMS`：公开 Release 只附公开资产的校验值。
- 单资产超过 2 GiB 时自动拆分为 `talentmind-code-<version>.tar.gz` 与 `talentmind-images-<version>.tar.gz`。

公开包不包含：真实 JD、MySQL dump、M2 私有 SQLite/原生报告、模型 Key、认证凭据、证书私钥、Cookie、Edge 档案和旧采集频率账本。私有数据包由负责人单独交付，不进入本 Release。

## 安装入口

1. 下载代码包（以及拆分时的镜像包）和 `SHA256SUMS`，先校验：
   ```bash
   sha256sum -c SHA256SUMS
   ```
2. 解压到同一根目录：
   ```bash
   sudo mkdir -p /opt/talentmind
   sudo tar -xzf talentmind-code-<version>.tar.gz -C /opt/talentmind
   # 仅拆分镜像时执行：
   sudo tar -xzf talentmind-images-<version>.tar.gz -C /opt/talentmind
   ```
3. 将负责人私有交付的数据包解压到同一根目录（`app/deploy/data/`、`app/deploy/seed/`、`app/deploy/model.env`、`app/deploy/m2/`）。
4. 执行安装：
   ```bash
   sudo bash /opt/talentmind/app/deploy/scripts/install.sh
   ```

`install.sh` 读取 `deploy/package.env` 选择镜像版本；数据包 seed 仅在 `data/backend` 为空时写入，目标非空会明确拒绝，避免覆盖已有运行数据。完整参数、TLS 模式、运维和故障排查见 [Ubuntu 生产部署与运行](部署与运行-Ubuntu.md)。

## 已验证范围（2026-11-20）

`20261118-1` 已在腾讯云 Ubuntu 24.04 服务器完成首次部署：

- MySQL/backend healthy、web up，HTTP→HTTPS 正常；MySQL 未暴露公网，noVNC 仅宿主机回环。
- Basic Auth 与七个页面已线上实际打开检查：
  - M1 数据采集：存量 2988 条 JD，数据库、状态、频率接口正常；三站均未开始真实采集（BOSS 进入用户页、智联游客内容受限、猎聘搜索页内容不足）。
  - 岗位机会雷达：搜索“金融数据工程师”返回 1 条，职责与技能详情可查看。
  - M2 分析：输入分页、历史运行读取、新旧已保存版本比较可用；新建分析与实际模型执行尚未验证。
  - 能力动态：已保存岗位变化记录可读取。
  - M3 岗位星云：历史交接图谱可用（7845 节点、11412 条关联），Python 节点可定位，222 条历史直接关系可查看；新 M2 结果尚未进入当前图谱。
  - 简历匹配：合成 TXT 解析成功，返回 3 个岗位推荐。
  - 学习路径：技能缺口、原 JD 依据与练习建议可显示；发现 `Apache Airflow` 被提取为 `apache` 的普通缺陷，待后续改进。
- 数据迁移核对：`jd_pool` 2988、`job_definition` 717、`job_skill` 717、`skill_dict` 285、`signal` 1540、`job_change_log` 275、`resume` 0、`talent_raw` 0；M2 `analysis.sqlite3` 与 `workflow.sqlite3` seed 已就位。
- 交付包 SHA256 与 `MANIFEST.json` 中 MySQL dump、`analysis.sqlite3`、`workflow.sqlite3` 三项摘要一致；隔离安装烟测中两个 SQLite 的 `PRAGMA integrity_check` 为 `ok`，安装后 MySQL 行数与 MANIFEST 一致。
- 包回归：`deploy/tests/test-package.sh` 校验 `SHA256SUMS`、公开包禁止路径、MANIFEST、SQLite 完整性，并拒绝 `app/deploy/**` 或 `app/scripts/*.sh` 中的 CRLF；完整烟测检查 `/healthz`、`/`、`/api/collection/platforms`、`/api/jobs`、`/api/m2/delivery/inputs`。

## 未完成与限制

- **M1**：真实浏览器采集及三站登录、DOM、CDP/插件配对继续暂缓，后续转为具备合法授权的数据 API 采集方案；当前不宣称已有 API 采集实现，也不声明持续新增 JD。
- **M2**：新分析的真实模型执行、保存与下游消费尚未验证；现有已保存运行的读取和版本比较可用。
- **M3**：当前使用历史交接图谱；新 M2 输出接入并改善真实图谱仍在后续阶段，不重新开启历史对照研究工程。
- **M4**：线上检查只使用合成 TXT，真实简历与匹配准确率未验证；扫描件、旧 DOC 仍需转换。
- **域名与 HTTPS**：当前公网 IP 使用自签证书，且公网 IP 不在证书 SAN 中；ICP 备案审核中，备案完成后配置正式域名、DNS 与受信任证书。备案等待不阻塞本 Release。
- 安装烟测在 Windows 宿主机 Docker 上执行，不代表全新云主机；真实服务器首次部署已完成，后续发布仍建议按实际变更做最小验证。
- 真实采集、正式数据库新写入和全量语义准确率均未验收，不得由本次发布推断。

## 私有数据与安全边界

- 公开 Release 不含任何 Key、Cookie、口令、认证凭据、证书私钥或真实 JD/简历。
- 私有数据包包含 MySQL dump、M2 私有 SQLite 与原生报告、历史 state、`model.env`、M2 `config.json`/`api-key.txt`，只私下交付并独立保管，不上传 GitHub。
- 部署后建议轮换模型 Key 和 Basic Auth 密码；私有数据包与备份按敏感材料保管。
