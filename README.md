# auto-switched-public

switched.cloud 每日 Cloud Token 自动领取 —— **只放 GitHub Actions 工作流**。

代码本体在私有库 [`jyucoeng/auto-switched-private`](https://github.com/jyucoeng/auto-switched-private)，
工作流运行时通过 Personal Access Token 检出。公开库跑 Actions 不计费。

---

## 相关站点（备用备忘）

| 用途 | 地址 |
|---|---|
| **控制面板 · 领取页** | https://panel.switched.cloud/tokens |
| **控制面板 · 首页** | https://panel.switched.cloud |
| SSO 统一登录 | https://accounts.noprofit.space/login |
| SSO 注册 | https://accounts.noprofit.space/register |
| SSO 账号中心 | https://accounts.noprofit.space/dashboard |
| noprofit 主站 | https://noprofit.space |
| 服务条款 | https://noprofit.space/terms |
| 隐私政策 | https://noprofit.space/privacy |
| 官方 Discord | https://discord.gg/DTGbwcJhCK |
| Vylo（短链广告商） | https://vylo.cc |
| sing-box 发布页 | https://github.com/SagerNet/sing-box/releases |

> 面板里有两个广告商入口：`Earn with Linkvertise` 和 `Earn with Vylo`。
> 本项目只走 **Vylo**，Linkvertise 那条是 40 分钟以上倒计时，不实用。

---

## 运行机制

| 项目 | 说明 |
|---|---|
| 触发 | 账号 #1 `10 01 * * *`、账号 #2 `40 01 * * *`（UTC，即北京 09:10 / 09:40） |
| 单次目标 | 一轮跑满当日上限 **25/25** |
| 收益 | 每个 Vylo 任务 **+2 token**，跑满 25 次 = **+50 token** |
| 实测耗时 | 25 次约 **44 分钟**（约 1.7 分钟/次），`timeout-minutes: 120` 足够 |
| 轮数 | `VYLO_ROUNDS`，默认 `1` = 一次跑满；想分几次跑就调大 |
| 并发 | `cancel-in-progress: true`，同账号有排队时新的直接取代旧的 |
| 退出码 | 跑满或当日已满都算 `0`，只有真异常才 `1` |

### 领取流程（代码做的事）

```
面板 /tokens → 点 Earn with Vylo
  → 跳 vylo.cc/<id>，等 Cloudflare Turnstile 通过
  → Step1 点 Continue
  → Step2 等 <b id="count"> 归零
  → 下滑点 Unlock → 页面变成 "Unlocked! ... tap Continue."
  → 上滑点 Continue → 再一次倒计时归零
  → 下滑点 Unlock → 页面变成 "Unlocked! ... tap Get link."
  → 上滑点 Get link → 自动回面板，+2 token，N/25 → N+1/25
```

重复到 `25/25`，面板会显示 `That's all for today.`

---

## 必须配置的 Secrets

`Settings → Secrets and variables → Actions → New repository secret`

| Secret | 说明 |
|---|---|
| `PRIVATE_REPO_TOKEN` | 私有库访问 token（classic PAT，**No expiration**，scope `repo`） |
| `SWITCHED_USER_<N>` | 第 N 个账号的用户名 |
| `SWITCHED_PASS_<N>` | 第 N 个账号的密码 |
| `PROXY_CONTENT_<N>` | 第 N 个账号的住宅代理 URL |
| `TG_TOKEN_<N>` | 第 N 个账号的 Telegram bot token（不配则不发通知） |
| `TG_CHAT_<N>` | 第 N 个账号的 Telegram chat id |

`<N>` 与工作流里的 `ACCOUNT_ID` 一一对应。

### 代理格式

```
hysteria2://<uuid>@<host>:<port>/?sni=<sni>&alpn=h3&insecure=1
```

也支持 `vless://` / `vmess://` / `trojan://` / `ss://` / `tuic://` / `socks5://`。

> **必须是住宅 IP**。机房 IP（ip-api 里 `hosting: true`）会被 Vylo 直接拒绝。
> 脚本启动时会自检出口 IP，不通过就中止，不会浪费额度。

---

## 多账号：一个账号一个 yml

账号之间完全隔离，互不影响。

### 当前已启用

| 工作流 | ACCOUNT_ID | 触发（UTC） |
|---|---|---|
| `switched-farm.yml` | `1` | `10 01` |
| `switched-farm-2.yml` | `2` | `40 01` |

### 加第 3 个账号

**第 1 步**：添加 5 个带 `_3` 后缀的 Secret

```
SWITCHED_USER_3
SWITCHED_PASS_3
PROXY_CONTENT_3
TG_TOKEN_3
TG_CHAT_3
```

**第 2 步**：复制工作流

```bash
cp .github/workflows/switched-farm.yml .github/workflows/switched-farm-3.yml
```

**第 3 步**：在新文件里改 3 处

| 位置 | 从 | 改成 |
|---|---|---|
| `name:` | `"🪙 Switched Token Farm #1"` | `"🪙 Switched Token Farm #3"` |
| `env.ACCOUNT_ID` | `'1'` | `'3'` |
| `env` 里 5 个变量名 | `SWITCHED_USER_1` 等 | `SWITCHED_USER_3` 等 |

具体是这 5 行：

```yaml
  SWITCHED_USER_3: ${{ secrets.SWITCHED_USER_3 }}
  SWITCHED_PASS_3: ${{ secrets.SWITCHED_PASS_3 }}
  PROXY_CONTENT_3: ${{ secrets.PROXY_CONTENT_3 }}
  TG_TOKEN_3: ${{ secrets.TG_TOKEN_3 }}
  TG_CHAT_3: ${{ secrets.TG_CHAT_3 }}
```

**第 4 步**：错开触发时间，避免同时跑

```yaml
- cron: '10 02 * * *'
```

### 不用改的地方（已按账号自动隔离）

| 项目 | 隔离方式 |
|---|---|
| 执行时间文件 | `switched/<ACCOUNT_ID>/time.txt`，各账号互不覆盖 |
| artifact 名 | `switched-logs-acct<N>-<run_id>` / `switched-shots-acct<N>-<run_id>` |
| 并发组 | `Switched_Token_Farm_<工作流名>`，每个 yml 独立，不会互相取消 |
| 代理端口 | 代码内 `free_port()` 自动避让，各账号从 10808 起找空闲端口 |
| sing-box 配置与日志 | 按 `ACCOUNT_ID` 分文件名，且**不进 artifact** |
| 通知 | 报告里带 `[#N]` 后缀，便于区分是哪个账号 |

---

## 目录结构

```
.
├── .github/workflows/
│   ├── switched-farm.yml      账号 #1
│   └── switched-farm-2.yml    账号 #2
├── switched/
│   ├── 1/time.txt             账号 #1 最近一次执行记录
│   └── 2/time.txt             账号 #2 最近一次执行记录
├── tools/
│   ├── gen-workflows.py       两个 yml 由同一模板生成，加账号只改这里
│   └── validate-workflows.py  提交前自检（YAML/表达式/bash/env 五项）
└── README.md
```

`switched/<N>/time.txt` 由工作流自动写入并提交：

```
账号: #1
时间: <本地时间>
UTC : <UTC 时间>
结果: <脚本退出码>
轮数: <VYLO_ROUNDS>
触发: <schedule 或 workflow_dispatch>
```

---

## 产物与日志

| artifact | 内容 |
|---|---|
| `switched-logs-acct<N>-<run_id>` | `*.log`、`stdout.log`、`summary.json` |
| `switched-shots-acct<N>-<run_id>` | 各阶段截图 `*.png` |

**不会上传**：sing-box 日志、`sing-box_config.json`（含代理地址与 UUID）。

三重保障：

1. 代码把 sing-box 日志写到系统临时目录，不落 `LOG_DIR`
2. 上传前 `find ... ! -iname '*sing-box*'` 过滤
3. 最后再 `rm -f` 兜底

---

## 依赖版本

私有库 `requirements.txt` 全部 `==` 精确锁定，避免上游发版导致 CI 行为漂移：

```
seleniumbase==4.54.2
selenium==4.49.0
pyvirtualdisplay==3.0
requests==2.34.2
```

---

## 手动触发

`Actions` → 选工作流 → `Run workflow`

| 输入 | 默认 | 说明 |
|---|---|---|
| `rounds` | `1` | 分几轮跑完，1 = 一次跑满 25/25 |
| `debug_html` | `1` | 失败时保存页面 HTML 便于排查 |
| `vylo_wait_max` | `600` | 单次任务最长等待秒数，任务慢时可临时放宽 |

---

## 改工作流的方式

**不要手工编辑 yml**，两个文件都由同一模板生成：

```bash
# 1. 改 tools/gen-workflows.py 里的 ACCOUNTS 列表或模板
vim tools/gen-workflows.py

# 2. 重新生成
python3 tools/gen-workflows.py

# 3. 提交前自检（五项全过才提交）
python3 tools/validate-workflows.py
```

`validate-workflows.py` 会检查：

| 检查项 | 挡住的坑 |
|---|---|
| YAML 语法 | 缩进、引号错误 |
| `${{ }}` 上下文名是否合法 | shell 变量误写成表达式 → dispatch 返回 422 |
| `${{ }}` 之外是否残留 `{{` 或 `}}` | shell 代码块变成 `{{ ... }}` → `exit 127` |
| 每个 `run` 脚本 `bash -n` | 脚本语法错误 |
| yml 环境变量 vs 代码 `env()` 读取 | 声明了没人读的死配置 / 代码要读却没声明 |

---

## 排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `⚠️ 未领取到` | 代理被判定为机房 IP | 换住宅代理，看日志里的 `出口` 行 |
| 卡在 `count=0` 不动 | 页面没刷新完成就点了 Unlock | 已加 12s 冷却 + 点击后确认，若复现收 artifact 排查 |
| `☑️ 今日已满额` | 当天额度已跑满 | 正常，次日 UTC 零点后重置 |
| 登录报 `credentials do not match` | 勾选框没勾上 / 触发限流 | 脚本已 JS 强制勾选 + 20 轮重试 |
| `exit_code` 为空 | `tee` 目标目录不存在 | 已改 `set +e` + 显式 `exit 0` |

---

## 站点规则

- 每日上限 **25 次 / 50 token**
- 每个 token 换取 1 天 Runtime（Plus 会员 2 天）
- 公平使用条款：禁止挖矿、DDoS / 端口扫描 / 爆破、垃圾信息，违规会封号
