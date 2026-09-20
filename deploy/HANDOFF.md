# ops-platform 部署交接（给国内机部署 agent）

更新：2026-09-20  
状态：代码已在 git；**GitHub 远端 URL 待用户创建空仓库后补上**；国内机 SSH 本机未打通。

## 代码位置

| 形式 | 路径 / 说明 |
|---|---|
| 本地 bare git | `C:\Users\tianxiang\git\ops-platform.git`（master @ `6cc2b6e`） |
| 源码包 | `C:\Users\tianxiang\git\ops-platform-master.tar.gz` |
| 工作副本 | `C:\Users\tianxiang\运维平台`（remote `ops-platform` → 上面 bare） |
| 特性文档 | 仓库内 `docs/compose/spec/ops-platform.md`（status=delivered） |
| 部署说明 | 仓库内 `deploy/DEPLOY_CN.md` |
| 验收脚本 | 仓库内 `deploy/verify_on_cn.sh` |

## 目标机（计划冻结，勿改）

- Tailscale：`xiaoze-hub@100.73.2.76` / 公网 `101.35.244.238`
- 平台端口：**8081**（PG 不映射宿主机端口）
- **禁止**：动 panwatch-postgres、占用 80/443、真实密码入仓、对生产容器乱试密码
- 生产 nginx：复用现有实例加 server 块（P5 / 28 号）

## 部署步骤（摘要，详见 DEPLOY_CN.md）

1. 上传 tarball 或 `git clone` 远端到 `~/apps/ops-platform`
2. 生成 `.env`（`DB_PASSWORD` / `SECRET_KEY` / `ADMIN_PASSWORD` 用 openssl rand；`PROJECT_DEPLOY_ENABLED=false`）
3. `docker compose up -d db platform`
4. `curl http://127.0.0.1:8081/api/v1/health`
5. login → change-password → register/heartbeat 验证节点 `verify-cn`
6. 负例：非法 action 必须 400

## 本机 agent 接入参数（验证用）

- `base_url=http://100.73.2.76:8081`
- `node_id` 建议：`domestic-cn` / `mini-host-win` / `hermes`
- 节点 token：部署时现生成，写入国内机 `.env`/配置，**不入仓**

## 待用户补充

- [ ] GitHub 空仓库 URL（用户建好后：`git remote add origin <url> && git push -u origin master`）
- [ ] 国内机 SSH 可用身份（部署 agent 侧自行具备）
