# -*- coding: utf-8 -*-
"""
从同一模板生成各账号的工作流，保证 env / 注释 / 步骤完全一致。

用法：
    python3 tools/gen-workflows.py

加账号时只改下面 ACCOUNTS 列表，然后重跑本脚本，不要手工编辑 yml。
改完执行：
    python3 -c "import yaml;yaml.safe_load(open('.github/workflows/switched-farm.yml'))"
确认 YAML 合法后再提交。
"""

TEMPLATE = '''\
# ───────────────────────────────────────────────────────────────
# 🪙 Switched Token Farm —— 账号 #{N}
#
# 代码在私有库 jyucoeng/auto-switched-private，用 PRIVATE_REPO_TOKEN 检出。
# 本仓库只放工作流；公开库的 Actions 分钟数不计费。
#
# ── 本文件用到的环境变量（全部会被 farm_switched.py 读取）──
#   ACCOUNT_ID          账号编号，决定读取 NAME_<ID> 后缀的变量
#   SWITCHED_USER_<N>   用户名        ← Secret
#   SWITCHED_PASS_<N>   密码          ← Secret
#   PROXY_CONTENT_<N>   住宅代理 URL  ← Secret
#   TG_TOKEN_<N>        TG bot token  ← Secret（可不配，不配不发通知）
#   TG_CHAT_<N>         TG chat id    ← Secret（可不配）
#   VYLO_ROUNDS         分几轮跑完，1 = 一次跑满当日上限 25/25
#   VYLO_WAIT_MAX       单次任务最长等待秒数
#   SOCKS_PORT          本地 socks 端口（被占用会自动避让）
#   SINGBOX_CFG         sing-box 配置文件名（默认 sing-box_config.json）
#   DEBUG_HTML          失败时是否保存页面 HTML
#   LOG_DIR / SCREENSHOT_DIR  产物目录（相对 app/）
#
#   ── VPS Runtime 自动续期（直接改这里的值，不用建 Secret）──
#   RENEW_ENABLED        1 开 / 0 关
#   RENEW_THRESHOLD_DAYS 剩余 Runtime <= 这个天数就自动续期（默认 5）
#   RENEW_MAX_TIMES      单次运行最多点几次 Add runtime（每次 +2 天 / -1 token）
#
# ── 再加一个账号要改什么 ──
#   1. 复制本文件为 switched-farm-{NEXT}.yml
#   2. 把文件里所有 _{N} 改成 _{NEXT}，name 里的 #{N} 改成 #{NEXT}
#   3. ACCOUNT_ID 改成 '{NEXT}'
#   4. cron 错开，例如 '10 02 * * *'
#   5. 到 Settings → Secrets 添加 _{NEXT} 结尾的 5 个密钥
#   并发组随工作流名自动隔离，artifact 名和 time 路径随 ACCOUNT_ID 自动隔离。
# ───────────────────────────────────────────────────────────────
name: "🪙 Switched Token Farm #{N}"

on:
  schedule:
    # {CRON_NOTE}
    - cron: '{CRON}'
  workflow_dispatch:
    inputs:
      rounds:
        description: '分几轮跑完（1 = 一次跑满 25/25）'
        required: false
        default: '1'
      debug_html:
        description: '失败时保存页面 HTML（1 开 / 0 关）'
        required: false
        default: '1'
      vylo_wait_max:
        description: '单次任务最长等待秒数'
        required: false
        default: '600'

# 同一账号的多余排队直接取消，避免堆积。
# 组名带工作流名，所以多账号之间互不取消。
concurrency:
  group: Switched_Token_Farm_${{{{ github.workflow }}}}
  cancel-in-progress: true

permissions:
  contents: write   # 需要提交 switched/<N>/time.txt

env:
  # ── 账号标识：每个 yml 填不同数字 ──
  ACCOUNT_ID: '{N}'

  # ── 该账号的凭证（Secret 名称必须带 _{N} 后缀）──
  {CREDS}

  # ── 运行参数（与代码里的 env() / env_int() 一一对应）──
  VYLO_ROUNDS: ${{{{ github.event.inputs.rounds || '1' }}}}
  VYLO_WAIT_MAX: ${{{{ github.event.inputs.vylo_wait_max || '600' }}}}
  DEBUG_HTML: ${{{{ github.event.inputs.debug_html || '1' }}}}
  SOCKS_PORT: '10808'
  SINGBOX_CFG: sing-box_config.json

  # ── VPS Runtime 自动续期（按需改这三个值即可，不需要 Secret）──
  RENEW_ENABLED: '1'
  RENEW_THRESHOLD_DAYS: '5'
  RENEW_MAX_TIMES: '3'

  LOG_DIR: logs
  SCREENSHOT_DIR: screenshots
  PYTHONUNBUFFERED: '1'
  TZ: Asia/Shanghai

jobs:
  farm:
    runs-on: ubuntu-latest
    timeout-minutes: 120

    steps:
      # ── 1) 公开库：只为了最后提交 switched/<N>/time.txt ──
      - name: 检出公开仓库
        uses: actions/checkout@v4

      # ── 2) 私有库：用 token 检出代码到 app/ ──
      - name: 检出私有代码库
        uses: actions/checkout@v4
        with:
          repository: jyucoeng/auto-switched-private
          token: ${{{{ secrets.PRIVATE_REPO_TOKEN }}}}
          path: app

      - name: 设置 Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip

      - name: 安装系统依赖
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y -qq \\
            xvfb unzip curl jq \\
            libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \\
            libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \\
            libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2
          # libasound2 在不同 Ubuntu 版本包名不同，单独兜底
          sudo apt-get install -y -qq libasound2t64 2>/dev/null \\
            || sudo apt-get install -y -qq libasound2 2>/dev/null || true

      # ── 3) 依赖全部走 requirements.txt 里的 == 精确版本 ──
      - name: 安装 Python 依赖
        run: |
          python -m pip install --upgrade pip
          pip install -r app/requirements.txt
          echo "===== 已安装版本 ====="
          pip list 2>/dev/null | grep -Ei 'seleniumbase|selenium|requests|pyvirtualdisplay'

      - name: 安装 sing-box
        run: |
          set -e
          ARCH=$(uname -m)
          case "$ARCH" in
            x86_64)  SB_ARCH=amd64 ;;
            aarch64) SB_ARCH=arm64 ;;
            *) echo "不支持的架构 $ARCH"; exit 1 ;;
          esac
          VER=$(curl -fsSL https://api.github.com/repos/SagerNet/sing-box/releases/latest \\
                | jq -r .tag_name | sed 's/^v//')
          echo "sing-box 版本: $VER ($SB_ARCH)"
          curl -fsSL -o /tmp/sb.tar.gz \\
            "https://github.com/SagerNet/sing-box/releases/download/v${VER}/sing-box-${VER}-linux-${SB_ARCH}.tar.gz"
          tar -xzf /tmp/sb.tar.gz -C /tmp
          cp "/tmp/sing-box-${VER}-linux-${SB_ARCH}/sing-box" app/sing-box
          chmod +x app/sing-box
          app/sing-box version

      - name: 语法检查
        run: python -m py_compile app/farm_switched.py app/gen_singbox_config.py

      - name: 准备输出目录
        working-directory: app
        run: mkdir -p "$LOG_DIR" "$SCREENSHOT_DIR"

      - name: 随机延迟
        run: sleep $((RANDOM % 90 + 20))

      # ── 4) 执行 ──
      - name: 执行刷币
        id: run
        continue-on-error: true
        working-directory: app
        run: |
          # 关掉 errexit：脚本非 0 也要把退出码写进 output，否则判定步骤读到空值
          set +e
          set -o pipefail
          mkdir -p "$LOG_DIR"
          python farm_switched.py 2>&1 | tee "$LOG_DIR/stdout.log"
          code=${PIPESTATUS[0]}
          echo "脚本退出码: $code"
          echo "exit_code=$code" >> "$GITHUB_OUTPUT"
          exit 0

      - name: 输出日志尾部
        if: always()
        run: |
          echo "===== 日志文件 ====="
          ls -la "app/$LOG_DIR" 2>/dev/null || echo "(空)"
          echo "===== 截图数量 ====="
          ls "app/$SCREENSHOT_DIR" 2>/dev/null | wc -l
          echo "===== 主日志尾部 ====="
          tail -80 "app/$LOG_DIR"/*.log 2>/dev/null || echo "(无)"
          echo "===== summary.json ====="
          cat "app/$LOG_DIR/summary.json" 2>/dev/null || echo "(无)"

      # ── 5) 只收集排查用文件；sing-box 日志与配置一律不进 artifact ──
      - name: 整理上传目录（排除 sing-box 日志与配置）
        if: always()
        run: |
          mkdir -p artifact/logs artifact/screenshots
          if [ -d "app/$LOG_DIR" ]; then
            find "app/$LOG_DIR" -maxdepth 1 -type f \\
              ! -iname '*sing-box*' ! -iname '*singbox*' \\
              -exec cp -f {{}} artifact/logs/ \\; 2>/dev/null || true
          fi
          if [ -d "app/$SCREENSHOT_DIR" ]; then
            find "app/$SCREENSHOT_DIR" -maxdepth 1 -type f -iname '*.png' \\
              -exec cp -f {{}} artifact/screenshots/ \\; 2>/dev/null || true
          fi
          # 兜底再删一次，任何形式的代理文件都不许混入
          rm -f artifact/logs/*sing-box* artifact/logs/*singbox*
          rm -f artifact/*sing-box_config.json
          echo "===== 待上传 =====" && ls -R artifact | head -30

      - name: 上传日志
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: switched-logs-acct${{{{ env.ACCOUNT_ID }}}}-${{{{ github.run_id }}}}
          path: artifact/logs
          if-no-files-found: warn
          retention-days: 7

      - name: 上传截图
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: switched-shots-acct${{{{ env.ACCOUNT_ID }}}}-${{{{ github.run_id }}}}
          path: artifact/screenshots
          if-no-files-found: warn
          retention-days: 7

      # ── 6) 记录执行时间（路径随 ACCOUNT_ID 隔离：switched/<N>/time.txt）──
      - name: 提交执行时间
        if: always()
        run: |
          TIME_DIR="switched/${ACCOUNT_ID}"
          TIME_FILE="${TIME_DIR}/time.txt"
          mkdir -p "$TIME_DIR"
          {
            echo "账号: #${ACCOUNT_ID}"
            echo "时间: $(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S %Z')"
            echo "UTC : $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
            echo "结果: ${{{{ steps.run.outputs.exit_code }}}}"
            echo "轮数: ${VYLO_ROUNDS}"
            echo "等待上限: ${VYLO_WAIT_MAX}s"
            echo "触发: ${{{{ github.event_name }}}}"
          } > "$TIME_FILE"
          cat "$TIME_FILE"
          git config user.name  "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add "$TIME_FILE"
          git diff --cached --quiet || git commit -m "chore: 账号 #${ACCOUNT_ID} 执行时间 $(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M')"
          git pull --rebase --autostash origin "${GITHUB_REF_NAME}" || true
          git push || echo "推送失败（可能无变更或权限不足）"

      - name: 清理旧运行
        if: always()
        continue-on-error: true
        env:
          GH_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
        run: |
          KEEP=5
          # 只清理本工作流的旧运行，且绝不删当前这一次
          RUNS=$(gh api "repos/${{{{ github.repository }}}}/actions/runs?per_page=100" \\
                 --jq ".workflow_runs[] | select(.name==\\"${{{{ github.workflow }}}}\\" and .id != ${{{{ github.run_id }}}}) | .id" \\
                 | tail -n +$((KEEP+1)))
          if [ -z "$RUNS" ]; then echo "无需清理"; exit 0; fi
          for id in $RUNS; do
            gh api -X DELETE "repos/${{{{ github.repository }}}}/actions/runs/$id" && echo "已删除 run $id"
          done

      # ── 7) 退出码判定（满额也走 exit 0，不算失败）──
      - name: 按脚本退出码判定结果
        if: always()
        run: |
          code="${{{{ steps.run.outputs.exit_code }}}}"
          echo "脚本退出码: ${code:-未知}"
          if [ "${code}" != "0" ]; then
            echo "::error::farm_switched.py 退出码 ${code}，请查看 switched-logs-acct${{{{ env.ACCOUNT_ID }}}} artifact"
            exit 1
          fi
'''

CRED_TMPL = '''SWITCHED_USER_{N}: ${{{{ secrets.SWITCHED_USER_{N} }}}}
  SWITCHED_PASS_{N}: ${{{{ secrets.SWITCHED_PASS_{N} }}}}
  PROXY_CONTENT_{N}: ${{{{ secrets.PROXY_CONTENT_{N} }}}}
  TG_TOKEN_{N}: ${{{{ secrets.TG_TOKEN_{N} }}}}
  TG_CHAT_{N}: ${{{{ secrets.TG_CHAT_{N} }}}}'''

ACCOUNTS = [
    dict(N="1", NEXT="2", CRON="10 01 * * *",
         CRON_NOTE="每天一次跑满 25/25。UTC 01:10 = 北京 09:10，已过 UTC 零点额度重置"),
    dict(N="2", NEXT="3", CRON="40 01 * * *",
         CRON_NOTE="每天一次跑满 25/25。UTC 01:40 = 北京 09:40，与账号 #1 错开 30 分钟"),
]

for a in ACCOUNTS:
    creds = CRED_TMPL.format(N=a["N"])
    out = (TEMPLATE
           .replace("{CREDS}", creds)
           .replace("{NEXT}", a["NEXT"])
           .replace("{N}", a["N"])
           .replace("{CRON_NOTE}", a["CRON_NOTE"])
           .replace("{CRON}", a["CRON"]))
    # 模板里为可读性写的 {{{{ }}}} / {{}} 在这里还原成 GitHub 表达式与 shell 花括号
    out = out.replace('{{}}', '\x00').replace('{{{{', '{{').replace('}}}}', '}}').replace('\x00', '{}')
    path = f"/Users/yux/Documents/GitHub/auto-switched-public/.github/workflows/switched-farm{'' if a['N']=='1' else '-'+a['N']}.yml"
    open(path, "w").write(out)
    print(f"✅ 生成 {path}")
