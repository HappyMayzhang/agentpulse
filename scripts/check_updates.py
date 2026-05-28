"""
check_updates.py — 半自动 SOTA 更新检查脚本

检查来源：
  1. Papers with Code API（有映射关系的 benchmark）
  2. 预设的 leaderboard 页面（关键数值抓取）

用法：
  python scripts/check_updates.py              # 只检查，打印报告
  python scripts/check_updates.py --apply      # 检查 + 自动写入 YAML
  python scripts/check_updates.py --ci         # CI 模式：有更新时写文件供 GitHub Actions 创建 PR

退出码：
  0 — 无更新
  1 — 发现更新（CI 模式下）
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).parent.parent
YAML_PATH = ROOT / "data" / "benchmarks.yaml"
SUMMARY_PATH = ROOT / "data" / "_pending_updates.json"

# ── Papers with Code API ──────────────────────────────────────────────────────
# 映射：benchmark 名称 → PwC benchmark slug
# 从 https://paperswithcode.com/sota/<task> 页面确认
PWC_BENCHMARK_MAP = {
    "HumanEval":         "humaneval",
    "MBPP":              "mbpp",
    "SWE-bench Verified": "swe-bench-verified",
    "GPQA Diamond":      "gpqa-diamond",
    "MMLU-Pro":          "mmlu-pro",
    "IFEval":            "ifeval",
    "GSM8K":             "gsm8k",
    "MATH-500":          "math-500",
}

PWC_API_BASE = "https://paperswithcode.com/api/v1"
PWC_HEADERS  = {"User-Agent": "agent-bench-tracker/1.0 (github.com/agent-bench-tracker)"}


def pwc_get_sota(benchmark_slug: str) -> dict | None:
    """查询 Papers with Code API，返回最新 SOTA 条目（分数最高的那条）"""
    url = f"{PWC_API_BASE}/sota/?benchmark={benchmark_slug}&format=json"
    try:
        resp = requests.get(url, headers=PWC_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("results", [])
        if not rows:
            return None
        # PwC 按分数降序排列，取第一条
        top = rows[0]
        return {
            "sota_score": _fmt_score(top.get("best_metric")),
            "sota_model": top.get("model_name", ""),
            "sota_date":  top.get("paper_date", "")[:7] if top.get("paper_date") else "",
            "source": f"Papers with Code / {benchmark_slug}",
        }
    except Exception as e:
        print(f"  [PwC] {benchmark_slug}: 请求失败 ({e})")
        return None


def _fmt_score(val) -> str:
    """把 PwC 返回的数值格式化为 '94.6%' 形式"""
    if val is None:
        return ""
    try:
        f = float(val)
        # PwC 有时返回小数（0.946），有时返回百分数（94.6）
        if f <= 1.0:
            f *= 100
        return f"{f:.1f}%"
    except (ValueError, TypeError):
        return str(val)


# ── Leaderboard scrapers ──────────────────────────────────────────────────────
# 每个 scraper 返回 {"sota_score": ..., "sota_model": ..., "sota_date": ...}
# 或 None（抓取失败）

def _extract_first_number(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def _extract_scores_in_range(text: str, lo: float, hi: float) -> list[float]:
    """从文本中提取在 [lo, hi] 范围内的所有百分比数值（过滤噪声）"""
    candidates = re.findall(r'\b(\d{1,3}\.\d{1,2})\b', text)
    return [float(s) for s in candidates if lo <= float(s) <= hi]


def scrape_swebench() -> dict | None:
    """
    从 swebench.com 抓取 Verified 榜首。
    SWE-bench Verified 历史区间大致 30-100%，取该范围内最大值。
    注意：页面为 JS 渲染，静态抓取可能拿不到完整数据，结果需人工确认。
    """
    try:
        resp = requests.get("https://www.swebench.com/", timeout=15,
                            headers={"User-Agent": PWC_HEADERS["User-Agent"]})
        resp.raise_for_status()
        scores = _extract_scores_in_range(resp.text, lo=30.0, hi=100.0)
        if scores:
            best = max(scores)
            return {
                "sota_score": f"{best:.1f}%",
                "sota_model": "",
                "sota_date":  "",
                "source": "swebench.com (JS渲染，需人工确认)",
            }
    except Exception as e:
        print(f"  [scraper] swebench.com: {e}")
    return None


def scrape_hle() -> dict | None:
    """
    从 Scale Labs HLE leaderboard 抓取榜首。
    HLE 历史区间大致 5-60%，取该范围内最大值。
    """
    try:
        resp = requests.get("https://labs.scale.com/leaderboard/humanitys_last_exam",
                            timeout=15,
                            headers={"User-Agent": PWC_HEADERS["User-Agent"]})
        resp.raise_for_status()
        scores = _extract_scores_in_range(resp.text, lo=5.0, hi=60.0)
        if scores:
            best = max(scores)
            return {
                "sota_score": f"{best:.1f}%",
                "sota_model": "",
                "sota_date":  "",
                "source": "labs.scale.com/leaderboard/humanitys_last_exam (需人工确认)",
            }
    except Exception as e:
        print(f"  [scraper] HLE leaderboard: {e}")
    return None


# 注册 leaderboard scrapers
LEADERBOARD_SCRAPERS = {
    "SWE-bench Verified": scrape_swebench,
    "HLE":                scrape_hle,
}


# ── Score comparison ──────────────────────────────────────────────────────────

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
        return True   # 之前没有数据，视为更新
    return n > o


# ── Core logic ────────────────────────────────────────────────────────────────

def check_all(data: dict) -> list[dict]:
    """
    检查所有 benchmark，返回有更新的条目列表
    每条格式：{category, name, old_score, new_score, new_model, new_date, source}
    """
    updates = []

    for cat in data.get("categories", []):
        for bm in cat.get("benchmarks", []):
            name = bm["name"]
            old_score = bm.get("sota_score", "") or ""
            print(f"  检查 {name} (当前 SOTA: {old_score or '—'})")

            fetched = None

            # 优先用 leaderboard scraper
            if name in LEADERBOARD_SCRAPERS:
                fetched = LEADERBOARD_SCRAPERS[name]()
                time.sleep(0.5)

            # 再尝试 Papers with Code
            if fetched is None and name in PWC_BENCHMARK_MAP:
                fetched = pwc_get_sota(PWC_BENCHMARK_MAP[name])
                time.sleep(0.3)

            if fetched is None:
                continue

            new_score = fetched.get("sota_score", "")
            if is_higher(new_score, old_score):
                updates.append({
                    "category":  cat["name"],
                    "name":      name,
                    "old_score": old_score or "—",
                    "new_score": new_score,
                    "new_model": fetched.get("sota_model", ""),
                    "new_date":  fetched.get("sota_date", ""),
                    "source":    fetched.get("source", ""),
                })

    return updates


def apply_updates(data: dict, updates: list[dict]) -> dict:
    """把 updates 写回 data dict"""
    index: dict[str, dict] = {}
    for cat in data.get("categories", []):
        for bm in cat.get("benchmarks", []):
            index[bm["name"]] = bm

    for u in updates:
        bm = index.get(u["name"])
        if bm is None:
            continue
        bm["sota_score"] = u["new_score"]
        if u["new_model"]:
            bm["sota_model"] = u["new_model"]
        if u["new_date"]:
            bm["sota_date"] = u["new_date"]

    return data


def print_report(updates: list[dict]):
    if not updates:
        print("\n未发现更新。")
        return
    print(f"\n发现 {len(updates)} 处更新：")
    print("-" * 70)
    for u in updates:
        model_str = f" ({u['new_model']})" if u['new_model'] else ""
        print(f"  [{u['category']}] {u['name']}")
        print(f"    {u['old_score']}  →  {u['new_score']}{model_str}")
        print(f"    来源: {u['source']}")
    print("-" * 70)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="自动写入 YAML")
    parser.add_argument("--ci",    action="store_true", help="CI 模式，写 _pending_updates.json")
    args = parser.parse_args()

    print(f"加载数据：{YAML_PATH}")
    with open(YAML_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    print("\n开始检查更新...\n")
    updates = check_all(data)
    print_report(updates)

    if not updates:
        sys.exit(0)

    if args.apply or args.ci:
        # 写回 YAML
        apply_updates(data, updates)
        with open(YAML_PATH, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        print(f"\nYAML 已更新：{YAML_PATH}")

    if args.ci:
        # 写 JSON 摘要供 GitHub Actions 创建 PR 描述
        with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(updates, f, ensure_ascii=False, indent=2)
        print(f"摘要已写入：{SUMMARY_PATH}")
        sys.exit(1)   # 告知 GitHub Actions 有变更，触发 PR 创建


if __name__ == "__main__":
    main()
