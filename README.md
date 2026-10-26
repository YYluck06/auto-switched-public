# auto-switched-public

switched.cloud Cloud Token 自动领取 —— **只放 GitHub Actions 工作流**。

代码本体在私有库 [`jyucoeng/auto-switched-private`](https://github.com/jyucoeng/auto-switched-private)，
本仓库的工作流通过 Personal Access Token（`PRIVATE_REPO_TOKEN`，无过期）在运行时检出。

> 为什么拆两个库：公开库跑 Actions **不计费**，私有库保存代码不外泄。

---

## 运行机制

| 项目 | 说明 |
|---|---|
| 触发 | 账号 #1：每天 **UTC 01:10 / 北京 09:10**；账号 #2：**UTC 01:40** |
| 单次目标 | 一轮跑满当日上限 **25/25**（每次任务 +2 token，共 **+50 token**） |
| 实测耗时 | 25 次任务约 **44 分钟**（约 1.7 分钟/次），`timeout-minutes: 120` 足够 |
| 并发 | `cancel-in-progress: true` —— 同一账号有排队时，新的直接取代旧的 |
| 轮数 | `VYLO_ROUNDS`，默认 `1` 表示一次跑满（想分多次跑就调大） |
| 退出码 | 任务成功或当日已满额都算 `0`，只有真异常才 `1` |

---

## 必须配置的 Secrets

`Settings → Secrets and variables → Actions → New repository secret`

| Secret | 说明 |
|---|---|
| `PRIVATE_REPO_TOKEN` | 私有库访问 token（**已配好**，classic PAT，**No expiration**，scope `repo`） |
| `SWITCHED_USER_1` | 账号 #1 用户名 |
| `SWITCHED_PASS_1` | 账号 #1 密码 |
| `PROXY_CONTENT_1` | 住宅代理，格式 `hysteria2://<uuid>@<host>:<port>/?sni=...&alpn=h3&insecure=1` |
| `TG_TOKEN_1` | 账号 #1 的 TG bot token |
| `TG_CHAT_1` | 账号 #1 的 TG chat id |

> 代理必须是**住宅 IP**。机房 IP（`hosting: true`）会被 Vylo 拒绝。

---

## 当前已启用的账号

| 工作流 | ACCOUNT_ID | 账号 | 触发时间（UTC） |
|---|---|---|---|
| `switched-farm.yml` | `1` | `yux***890` | `10 01`（北京 09:10） |
| `switched-farm-2.yml` | `2` | `hsi***ulu` | `40 01`（北京 09:40） |

两个账号共用同一个住宅代理和同一个 TG 会话，报告靠 `[#1]` / `[#2]` 后缀区分。

---

## 多账号：加一个账号要改哪些东西

采用**一个账号一个 yml** 的模式，账号之间完全隔离，互不影响。

### 第 1 步：添加 5 个带 `_2` 后缀的 Secret

```
SWITCHED_USER_2
SWITCHED_PASS_2
PROXY_CONTENT_2
TG_TOKEN_2
TG_CHAT_2
```

### 第 2 步：新建工作流文件

```bash
cp .github/workflows/switched-farm.yml .github/workflows/switched-farm-2.yml
```

然后在这个新文件里改 **3 个地方**：

| 位置 | 账号 #1 的值 | 改成 |
|---|---|---|
| `name:` | `"🪙 Switched Token Farm #1"` | `"🪙 Switched Token Farm #2"` |
| `env.ACCOUNT_ID` | `'1'` | `'2'` |
| `env` 里 5 个变量名 | `SWITCHED_USER_1` 等 | `SWITCHED_USER_2` 等 |

具体是这 5 行：

```yaml
  SWITCHED_USER_2: ${{ secrets.SWITCHED_USER_2 }}
  SWITCHED_PASS_2: ${{ secrets.SWITCHED_PASS_2 }}
  PROXY_CONTENT_2: ${{ secrets.PROXY_CONTENT_2 }}
  TG_TOKEN_2: ${{ secrets.TG_TOKEN_2 }}
  TG_CHAT_2: ${{ secrets.TG_CHAT_2 }}
```

> 仓库里已放好 `.github/workflows/switched-farm-2.yml.example`，
> 直接去掉 `.example` 后缀即可，里面已经全部替换成 `_2`。

### 第 3 步（可选）：调整触发时间

多个账号同时跑容易互相干扰，建议错开：

```yaml
# switched-farm.yml      账号 #1
- cron: '10 01 * * *'
# switched-farm-2.yml    账号 #2
- cron: '40 01 * * *'
# switched-farm-3.yml    账号 #3
- cron: '10 02 * * *'
```

### 不用改的地方（已按账号自动隔离）

| 项目 | 隔离方式 |
|---|---|
| 执行时间文件 | 账号 #1 写 `time.txt`，账号 #2 写 `time_2.txt`，依次类推 |
| artifact 名 | `switched-logs-acct1-<run_id>` / `switched-logs-acct2-<run_id>` |
| 并发组 | `Switched_Token_Farm_<工作流名>`，每个 yml 独立，不会互相取消 |
| 代理端口 | 代码内 `free_port()` 自动避让，各账号从 10808 起找空闲端口 |
| sing-box 配置/日志 | 按 `ACCOUNT_ID` 分文件名，且**不进 artifact** |
| TG 报告 | 报告里会带 `[#2]` 后缀，便于区分是哪个账号 |

---

## 产物与日志

| 文件 | 内容 |
|---|---|
| `time.txt` / `time_<ID>.txt` | 每个账号最近一次执行时间、结果、退出码 |
| `switched-logs-acct<ID>-<run_id>` | `logs/*.log`、`logs/*.json`、失败时 `logs/err_*.html` |
| `switched-shots-acct<ID>-<run_id>` | 各阶段截图 `screenshots/*.png` |

**不会上传**：`sing-box` 日志、`sing-box_config.json`（含代理地址 / UUID）。
上传前有一道 `find ... ! -iname '*sing-box*'` 过滤 + 一次兜底 `rm`。

---

## 依赖版本

`app/requirements.txt` 全部使用 `==` 精确锁定，避免上游发版导致 CI 行为漂移：

```
seleniumbase==4.54.2
selenium==4.49.0
pyvirtualdisplay==3.0
requests==2.34.2
```

---

## TG 通知样例

**一次跑满：**

```
🪙 Switched Token 领取报告

🕐 运行时间: 2026-10-27 09:12:44
📊 领取结果: ✅ 一次领满
👤 账号: yux***890
🎁 本次奖励: +50 token
💰 余额: 50 token
📈 今日Vylo进度: 25/25 ✅

🌐 IP 信息: 185.156.53.*** (UA) [✅ 代理]
```

**当天重复执行发现已满额：**

```
📊 领取结果: ☑️ 今日已满额 25/25
🎁 本次奖励: +0 token
💰 余额: 50 token
📈 今日Vylo进度: 25/25 ✅
```

---

## 手动触发

`Actions` → `🪙 Switched Token Farm #1` → `Run workflow`

| 输入 | 默认 | 说明 |
|---|---|---|
| `rounds` | `1` | 分几轮跑完，1 = 一次跑满 25/25 |
| `debug_html` | `1` | 失败时保存页面 HTML 便于排查 |

---

## 实测记录

| 项 | 账号 #2（新注册 `hsiangyulu`，额度 0/25 起步） |
|---|---|
| 运行结果 | ✅ 全部 18 步通过，job `success` |
| 耗时 | 44 分钟 |
| 领取 | `0/25` → **`25/25`**，余额 `0` → **`50` token** |
| History | 25 条 `Vylo link completed / +2`，合计 `+50` |
| TG 报告 | `📊 领取结果: ✅ 一次领满` / `🎁 本次奖励: +50 token` / `📈 今日Vylo进度: 25/25 ✅` |
| artifact | 仅 `*.log` / `stdout.log` / `summary.json`，无 sing-box 日志、无代理地址与密码 |
| time 文件 | `time_2.txt`，`结果: 0` |

---

## 限制

- 每日上限 25 次 = 50 token，跑满后面板显示 `That's all for today.`
- 单次任务约 50~70 秒，25 次约 25~30 分钟，`timeout-minutes: 120` 足够
- 站点公平使用条款：禁止挖矿、DDoS / 端口扫描 / 爆破、垃圾信息，违规会封号
