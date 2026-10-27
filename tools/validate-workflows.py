#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提交前校验所有工作流，能挡住这次踩过的全部坑：

  1. YAML 语法
  2. ${{ }} 里的上下文名是否合法（防止 shell 变量被写成表达式 → dispatch 422）
  3. ${{ }} 之外是否残留 {{ 或 }}（防止 shell 代码块被写成 {{ ... }} → exit 127）
  4. 每个 run 脚本能否通过 bash -n
  5. yml 声明的环境变量与代码读取的是否一一对应

用法：
    python3 tools/validate-workflows.py
退出码 0 = 全部通过。
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WF_DIR = ROOT / ".github" / "workflows"
VALID_CONTEXTS = {
    "github", "env", "secrets", "steps", "inputs", "job",
    "runner", "matrix", "vars", "needs", "strategy",
}
# 这些是给 shell / 运行时用的，不参与"代码是否读取"的比对
SHELL_ONLY = {"PYTHONUNBUFFERED", "TZ"}
# 代码里带默认值、可不声明
OPTIONAL = {"SINGBOX_CFG"}

errors: list[str] = []


def check_yaml(p: Path, text: str):
    try:
        return yaml.safe_load(text)
    except Exception as e:
        errors.append(f"{p.name}: YAML 解析失败 -> {e}")
        return None


def check_expressions(p: Path, text: str):
    for m in re.finditer(r"\$\{\{\s*([A-Za-z_][A-Za-z0-9_\-]*)", text):
        if m.group(1) not in VALID_CONTEXTS:
            line = text[: m.start()].count("\n") + 1
            errors.append(
                f"{p.name}:{line}: 非法的表达式上下文 '{m.group(1)}'"
                f"（shell 变量请写成 ${{{m.group(1)}}}）"
            )


def check_stray_braces(p: Path, text: str):
    stripped = re.sub(r"\$\{\{.*?\}\}", "", text)
    for i, line in enumerate(stripped.split("\n"), 1):
        if "{{" in line or "}}" in line:
            errors.append(f"{p.name}:{i}: 残留双花括号 -> {line.strip()[:70]}")


def check_bash(p: Path, doc: dict):
    steps = (doc.get("jobs") or {}).get("farm", {}).get("steps", []) or []
    for idx, st in enumerate(steps, 1):
        script = st.get("run")
        if not script:
            continue
        # GitHub 表达式换成占位符，否则 bash 会当成坏替换
        script = re.sub(r"\$\{\{.*?\}\}", "__EXPR__", script)
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write(script)
            path = f.name
        r = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
        os.unlink(path)
        if r.returncode != 0:
            errors.append(
                f"{p.name}: 步骤{idx}「{st.get('name')}」bash -n 失败 -> "
                f"{r.stderr.strip().splitlines()[0] if r.stderr.strip() else ''}"
            )


def code_env_reads() -> set[str] | None:
    """从私有库代码里提取 env()/env_int()/os.environ.get() 读取的变量名"""
    private = ROOT.parent / "auto-switched-private"
    if not private.is_dir():
        return None
    code = ""
    for name in ("farm_switched.py", "gen_singbox_config.py"):
        f = private / name
        if f.exists():
            code += f.read_text(encoding="utf-8", errors="ignore")
    reads = set(re.findall(r'env(?:_int|_float|_flag)?\("([A-Z_]+)"', code))
    reads |= set(re.findall(r'os\.environ\.get\("([A-Z_]+)"', code))
    return reads or None


def check_env(p: Path, doc: dict, reads: set[str] | None):
    if reads is None:
        print(f"  ℹ️  {p.name}: 未找到私有库，跳过环境变量比对")
        return
    declared = {re.sub(r"_\d+$", "", k) for k in (doc.get("env") or {})}
    missing = reads - declared - OPTIONAL
    extra = declared - reads - SHELL_ONLY
    if missing:
        errors.append(f"{p.name}: 代码要读但 yml 未声明 -> {sorted(missing)}")
    if extra:
        errors.append(f"{p.name}: yml 声明了但代码不读（死配置）-> {sorted(extra)}")


def main() -> int:
    files = sorted(WF_DIR.glob("*.yml"))
    if not files:
        print("没找到工作流文件")
        return 1
    reads = code_env_reads()
    for p in files:
        text = p.read_text(encoding="utf-8")
        doc = check_yaml(p, text)
        check_expressions(p, text)
        check_stray_braces(p, text)
        if doc:
            check_bash(p, doc)
            check_env(p, doc, reads)

    if errors:
        print(f"\n❌ 发现 {len(errors)} 个问题：\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"\n✅ {len(files)} 个工作流全部通过")
    for p in files:
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        env = doc.get("env") or {}
        print(f"   {p.name}: ACCOUNT_ID={env.get('ACCOUNT_ID')} "
              f"cron={(doc.get(True) or {}).get('schedule', [{}])[0].get('cron')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
