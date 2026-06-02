"""
check_updates.py — AgentPulse SOTA 更新检查脚本

数据来源（7/7 benchmark 全自动）：
  llm-stats.com REST API   → SWE-bench Verified / Terminal-Bench 2.0 / OSWorld / Toolathlon / τ-bench
  HuggingFace parquet      → GAIA（gaia-benchmark/results_public）
  Google Sheets CSV        → WebArena（官方 leaderboard）

用法：
  python scripts/check_updates.py              # 只检查，打印报告
  python scripts/check_updates.py --apply      # 检查 + 自动写入 YAML
  python scripts/check_updates.py --ci         # CI 模式：有更新时退出码 1，供 GitHub Actions 创建 PR

环境变量：
  LLM_STATS_API_KEY   llm-stats.com API key（本地放 .env，CI 放 GitHub Secret）
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date as _date
from pathlib import Path

import io

import requests
import yaml

try:
    import pyarrow.parquet as pq
    _HAS_PYARROW = True
except ImportError:
    _HAS_PYARROW = False

# ── 加载 .env（本地开发用）──────────────────────────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

ROOT          = Path(__file__).parent.parent
YAML_PATH     = ROOT / "data" / "benchmarks.yaml"
SUMMARY_PATH  = ROOT / "data" / "_pending_updates.json"
PR_BODY_PATH  = ROOT / "data" / "_pr_body.md"
HISTORY_DIR   = ROOT / "data" / "history"


def name_to_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def append_history(name: str, score: str, model: str, bm_date: str) -> None:
    """把旧 SOTA 追加到历史记录文件（在覆盖更新之前调用）"""
    if not score:
        return
    slug = name_to_slug(name)
    path = HISTORY_DIR / f"{slug}.yaml"
    entry = {
        "score":       score,
        "model":       model or "",
        "date":        bm_date or "",
        "recorded_at": _date.today().isoformat(),
    }
    history = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            history = yaml.safe_load(f) or []
    # 避免重复追加相同记录
    if history and history[-1].get("score") == score and history[-1].get("model") == model:
        return
    history.append(entry)
    HISTORY_DIR.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(history, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

API_BASE = "https://api.llm-stats.com"

# ── benchmark 名称 → llm-stats benchmark ID ──────────────────────────────────
LLM_STATS_ID_MAP = {
    "SWE-bench Verified": "swe-bench-verified",
    "Terminal-Bench 2.0": "terminal-bench-2",
    "OSWorld":            "osworld",
    "Toolathlon":         "toolathlon",
    "τ-bench":            "tau-bench",
}

# llm-stats 未收录且无自动数据源的 benchmark（目前已全部自动化）
MANUAL_CHECK: dict[str, str] = {}

# ── WebArena：官方 Google Sheets leaderboard CSV ─────────────────────────────
_WEBARENA_CSV = (
    "https://docs.google.com/spreadsheets/d/"
    "1M801lEpBbKSNwP-vDBkC_pF7LdyGU1f_ufZb_NWNBZQ/export?format=csv"
)


def fetch_webarena_sota() -> dict | None:
    """从 WebArena 官方 Google Sheets leaderboard 拉取最高分"""
    import csv as _csv
    try:
        r = requests.get(_WEBARENA_CSV, timeout=15)
        r.raise_for_status()
        reader = _csv.DictReader(r.text.splitlines())
        best: dict | None = None
        best_score = -1.0
        for row in reader:
            try:
                score = float(row.get("Success Rate (%)", "").strip())
            except ValueError:
                continue
            if score > best_score:
                best_score = score
                best = row
        if best is None:
            return None
        # 日期格式 "02/2026" → "2026-02"
        raw_date = best.get("a", "").strip()
        try:
            month, year = raw_date.split("/")
            iso_date = f"{year}-{month.zfill(2)}"
        except Exception:
            iso_date = raw_date
        is_self_reported = "self-reported" in best.get("Result Source", "").lower()
        return {
            "sota_score":       f"{best_score:.1f}%",
            "sota_model":       best.get("Model", "").strip(),
            "sota_date":        iso_date,
            "is_self_reported": is_self_reported,
            "source":           "docs.google.com / WebArena leaderboard",
        }
    except Exception as e:
        print(f"  [WebArena 获取错误] {e}")
        return None

# ── GAIA：直接读 HuggingFace parquet ────────────────────────────────────────
_GAIA_PARQUET = (
    "https://huggingface.co/datasets/gaia-benchmark/results_public"
    "/resolve/refs%2Fconvert%2Fparquet/2023/test/0000.parquet"
)


def fetch_gaia_sota() -> dict | None:
    """从 HuggingFace gaia-benchmark/results_public 拉取 GAIA test SOTA"""
    if not _HAS_PYARROW:
        print("  [GAIA 跳过] 缺少 pyarrow，请运行：pip install pyarrow")
        return None
    try:
        r = requests.get(_GAIA_PARQUET, timeout=30)
        r.raise_for_status()
        table = pq.read_table(io.BytesIO(r.content))
        d = table.to_pydict()
        raw_scores = d.get("score", [])
        scores = [float(s) if s is not None else -1.0 for s in raw_scores]
        if not scores:
            return None
        idx = max(range(len(scores)), key=lambda i: scores[i])
        model = str((d.get("model") or [""])[idx] or "")
        date  = str((d.get("date") or [""])[idx] or "")
        return {
            "sota_score":       f"{scores[idx] * 100:.1f}%",
            "sota_model":       model,
            "sota_date":        date[:7],
            "is_self_reported": True,
            "source":           "huggingface.co / gaia-benchmark/results_public",
        }
    except Exception as e:
        print(f"  [GAIA 获取错误] {e}")
        return None


# 自定义 fetcher：benchmark name → fetch 函数（签名：() -> dict | None）
CUSTOM_FETCHERS = {
    "GAIA":     fetch_gaia_sota,
    "WebArena": fetch_webarena_sota,
}


def get_api_key() -> str:
    key = os.environ.get("LLM_STATS_API_KEY", "")
    if not key:
        print("错误：未找到 LLM_STATS_API_KEY，请在 .env 或环境变量中设置")
        sys.exit(1)
    return key


def fetch_top_score(benchmark_id: str, api_key: str) -> dict | None:
    """从 llm-stats API 拉取指定 benchmark 的最高分条目"""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        r = requests.get(
            f"{API_BASE}/stats/v1/scores",
            headers=headers,
            params={"benchmark": benchmark_id, "limit": 1},
            timeout=10,
        )
        r.raise_for_status()
        scores = r.json().get("scores", [])
        if not scores:
            return None
        top = scores[0]
        return {
            "sota_score":      f"{top['score'] * 100:.1f}%",
            "sota_model":      top.get("model_name", ""),
            "sota_date":       top.get("scored_at", "")[:7],
            "is_self_reported": top.get("is_self_reported", True),
            "source":          f"llm-stats.com / {benchmark_id}",
        }
    except Exception as e:
        print(f"  [API 错误] {benchmark_id}: {e}")
        return None


def score_to_float(s: str) -> float | None:
    if not s:
        return None
    try:
        return float(s.rstrip("%"))
    except ValueError:
        return None


def is_higher(new_score: str, old_score: str) -> bool:
    n = score_to_float(new_score)
    o = score_to_float(old_score)
    if n is None:
        return False
    if o is None:
        return True
    return n > o


def check_all(data: dict, api_key: str) -> tuple[list[dict], list[str]]:
    updates       = []
    manual_needed = []

    for cat in data.get("categories", []):
        for bm in cat.get("benchmarks", []):
            name      = bm["name"]
            old_score = bm.get("sota_score", "") or ""

            if name in MANUAL_CHECK:
                manual_needed.append(name)
                continue

            if name in CUSTOM_FETCHERS:
                print(f"  检查 {name} (当前 SOTA: {old_score or '—'})")
                fetched = CUSTOM_FETCHERS[name]()
            else:
                bm_id = LLM_STATS_ID_MAP.get(name)
                if bm_id is None:
                    print(f"  [跳过] {name}：未配置数据源")
                    continue
                print(f"  检查 {name} (当前 SOTA: {old_score or '—'})")
                fetched = fetch_top_score(bm_id, api_key)
                time.sleep(0.3)

            if fetched and is_higher(fetched["sota_score"], old_score):
                updates.append({
                    "category":        cat["name"],
                    "name":            name,
                    "old_score":       old_score or "—",
                    "new_score":       fetched["sota_score"],
                    "new_model":       fetched["sota_model"],
                    "new_date":        fetched["sota_date"],
                    "is_self_reported": fetched.get("is_self_reported", True),
                    "source":          fetched["source"],
                })

    return updates, manual_needed


def apply_updates(data: dict, updates: list[dict]) -> dict:
    index = {bm["name"]: bm
             for cat in data.get("categories", [])
             for bm in cat.get("benchmarks", [])}
    for u in updates:
        bm = index.get(u["name"])
        if bm is None:
            continue
        # 先把旧 SOTA 存入历史记录
        append_history(
            u["name"],
            bm.get("sota_score", "") or "",
            bm.get("sota_model", "") or "",
            bm.get("sota_date", "") or "",
        )
        bm["sota_score"] = u["new_score"]
        if u["new_model"]:
            bm["sota_model"] = u["new_model"]
        if u["new_date"]:
            bm["sota_date"] = u["new_date"]
        if "is_self_reported" in u:
            bm["is_self_reported"] = u["is_self_reported"]
    return data


def generate_pr_body(updates: list[dict], manual_needed: list[str]) -> str:
    today = _date.today().isoformat()
    rows = "\n".join(
        "| {name} | {old} | {new} | {model} | {src} |".format(
            name=u["name"],
            old=u["old_score"],
            new=u["new_score"],
            model=u["new_model"] or "—",
            src=u["source"],
        )
        for u in updates
    )
    body = f"""## AgentPulse SOTA 自动更新 — {today}

自动检测到 **{len(updates)}** 个 benchmark 出现新 SOTA，已写入 `data/benchmarks.yaml`。

### 更新详情

| Benchmark | 旧 SOTA | 新 SOTA | 模型 | 来源 |
|-----------|---------|---------|------|------|
{rows}
"""
    if manual_needed:
        links = "\n".join(f"- {n}：{MANUAL_CHECK[n]}" for n in manual_needed)
        body += f"\n### 需人工检查（llm-stats 未收录）\n\n{links}\n"

    body += "\n---\n*由 GitHub Actions 自动生成，请 review 后合并。*\n"
    return body


def print_report(updates: list[dict], manual_needed: list[str]):
    if updates:
        print(f"\n发现 {len(updates)} 处更新：")
        print("-" * 65)
        for u in updates:
            model_str = f" ({u['new_model']})" if u["new_model"] else ""
            print(f"  [{u['category']}] {u['name']}")
            print(f"    {u['old_score']}  →  {u['new_score']}{model_str}")
            print(f"    来源: {u['source']}")
        print("-" * 65)
    else:
        print("\n自动检查：未发现更新。")

    if manual_needed:
        print(f"\n以下 {len(manual_needed)} 个 benchmark 需人工检查（llm-stats 未收录）：")
        for name in manual_needed:
            print(f"  {name:20} → {MANUAL_CHECK[name]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply",        action="store_true", help="自动写入 YAML")
    parser.add_argument("--ci",           action="store_true", help="CI 模式")
    parser.add_argument("--init-history", action="store_true", help="从当前 YAML 初始化历史记录文件")
    args = parser.parse_args()

    api_key = get_api_key() if not args.init_history else ""

    print(f"加载数据：{YAML_PATH}")
    with open(YAML_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if args.init_history:
        count = 0
        for cat in data.get("categories", []):
            for bm in cat.get("benchmarks", []):
                append_history(
                    bm["name"],
                    bm.get("sota_score", "") or "",
                    bm.get("sota_model", "") or "",
                    bm.get("sota_date", "") or "",
                )
                count += 1
        print(f"历史记录初始化完成：{count} 个 benchmark → {HISTORY_DIR}")
        sys.exit(0)

    print("\n开始检查更新...\n")
    updates, manual_needed = check_all(data, api_key)
    print_report(updates, manual_needed)

    if not updates:
        sys.exit(0)

    if args.apply or args.ci:
        apply_updates(data, updates)
        with open(YAML_PATH, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        print(f"\nYAML 已更新：{YAML_PATH}")

    if args.ci:
        with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(updates, f, ensure_ascii=False, indent=2)
        print(f"摘要已写入：{SUMMARY_PATH}")
        pr_body = generate_pr_body(updates, manual_needed)
        with open(PR_BODY_PATH, "w", encoding="utf-8") as f:
            f.write(pr_body)
        print(f"PR body 已写入：{PR_BODY_PATH}")
        sys.exit(1)


if __name__ == "__main__":
    main()
