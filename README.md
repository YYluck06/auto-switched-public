# auto-switched-public

switched.cloud 每日 Cloud Token 自动领取 —— **只放 GitHub Actions 工作流**。

代码本体在私有库 [`jyucoeng/auto-switched-private`](https://github.com/jyucoeng/auto-switched-private)，
工作流运行时通过 Personal Access Token 检出。公开库跑 Actions 不计费。

---

## 相关站点

[控制面板](https://panel.switched.cloud)

---

## 运行机制

| 项目 | 说明 |
|---|---|
| 触发 | 账号 #1 `10 01 * * *`、账号 #2 `40 01 * * *`（UTC，即北京 09:10 / 09:40） |
| 附加动作 | 刷币结束后自动检查 VPS Runtime，低于阈值就续期（见下节） |
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

## VPS Runtime 自动续期

刷币跑完后，脚本会打开[控制面板的 VPS 页](https://panel.switched.cloud/vps)，逐台检查剩余 Runtime。
只有在 **「当前 Runtime + 本次续期的 2 天 ≤ 阈值」** 时才点 `Add runtime`
（一次 `+2 天`，消耗 `1 Cloud Token`）。

换句话说，`RENEW_THRESHOLD_DAYS` 是**上限**：续期后的 Runtime 绝不会超过它。

### 三个参数（直接改 yml 里的 `env`，不用建 Secret）

| 变量 | 默认 | 说明 |
|---|---|---|
| `RENEW_ENABLED` | `1` | `1` 开 / `0` 关，关掉就只刷币不续期 |
| `RENEW_THRESHOLD_DAYS` | `5` | **续期后 Runtime 的上限**；加完 2 天会超过它就不续 |
| `RENEW_MAX_TIMES` | `3` | 单次运行最多点几次，防止 token 被一次性抽干 |

### 续期逻辑

```
读取 /vps 列表
  └─ 无实例 → 报告写「无vps」，直接结束
  └─ 有实例 → 逐台进详情页
        └─ 当前 Runtime + 2 天 ≤ RENEW_THRESHOLD_DAYS ?
              ├─ 否 → 不续期（续了就会超上限）
              └─ 是 → 点 Add runtime → 弹窗确认（数量固定 1）→ 重新读 Runtime
                    └─ 再加 2 天仍不超上限且未满 RENEW_MAX_TIMES → 再续一次
```

阈值 `5` 天时的行为：

| 当前 Runtime | 续期后 | 是否续 | 最终 |
|---|---|---|---|
| `0d 12h` | `2d 12h` → `4d 12h` → `6d 12h` ❌ | 续 2 次 | `4d 12h` |
| `1d 0h` | `3d 0h` → `5d 0h` → `7d 0h` ❌ | 续 2 次 | `5d 0h` |
| `2d 19h` | `4d 19h` → `6d 19h` ❌ | 续 1 次 | `4d 19h` |
| `3d 0h` | `5d 0h` → `7d 0h` ❌ | 续 1 次 | `5d 0h` |
| `3d 12h` | `5d 12h` ❌ | 不续 | `3d 12h` |
| `4d 0h` | `6d 0h` ❌ | 不续 | `4d 0h` |
| `8d 18h` | `10d 18h` ❌ | 不续 | `8d 18h` |

> 边界是**包含**的：`3d 0h + 2d = 5d`，等于阈值，允许续期。
>
> 想囤更多天数就把 `RENEW_THRESHOLD_DAYS` 调大，但同时要留意
> `RENEW_MAX_TIMES` 会限制单次运行最多续几次（默认 3 次 = 最多 +6 天）。

### 与刷币完全隔离

| 场景 | 行为 |
|---|---|
| 刷币全部失败 | 仍执行续期 |
| 刷币抛异常中断 | 异常分支里补跑一次续期，然后才退出 |
| 续期自身异常 | 只记录到 `⚠️ 异常阶段`，刷币结果与退出码不受影响 |
| token 余额为 0 | 弹窗里读到 `You have 0 Cloud Tokens` 就取消，不乱点 |
| 页面加载失败 | 列表页/详情页各重试 3~4 次；仍失败则报告 `⚠️ 续期检查失败`，**不会**伪装成「无vps」 |

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

> 续期阈值不走 `workflow_dispatch` 输入，直接改 yml 的 `env` 即可。

---

## 改工作流的方式

两个 yml 相互独立，直接改各自的文件即可。加账号时复制一份、把 `_<N>` 后缀和
`ACCOUNT_ID` 改掉、再错开 cron。

### 提交前建议自查

| 检查项 | 怎么查 |
|---|---|
| YAML 语法 | 在 GitHub 网页上编辑时右侧会报错；本地 `python3 -c "import yaml;yaml.safe_load(open('文件'))"` |
| `${{ }}` 写成单花括号 | shell 变量必须写 `${VAR}`，写成 `${{VAR}}` 会被当成表达式，dispatch 直接 422 |
| 双花括号残留 | shell 的 `{ ... }` 代码块不能写成 `{{ ... }}`，否则 `exit 127` |
| cron 冲突 | 两个账号的 cron 至少错开 30 分钟 |

---|---|
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
