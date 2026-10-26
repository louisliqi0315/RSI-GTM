"""Phase 2b 缺口 4：T1 评估骨架 + 持续性基线 + 合成面板测试。

T1 任务（接 public_signal_panel.md §3）：预测下周 openrouter_share_direction
（up / flat / down），基线为朴素持续性基线（上周方向 = 下周方向）。
本文件不做任何真实数据宣称：

- `persistence_accuracy(rows)`：在面板行序列上算持续性基线的方向准确率，
  分别报告全部周与非发布周（排除 model_release_count > 0 的周，见 F2）。
- `majority_accuracy(rows)`：多数类基线（始终预测训练期最常见的方向）。
- `synthetic_panel(...)`：生成带已知持续性的合成面板（方向马尔可夫链，
  持续概率 p），用于检验基线代码本身：p=0.8 时持续性基线准确率应接近 0.8，
  p=1/3（随机三类）时应接近 1/3。合成面板不是真实数据，文件与行中均标注。
- `validate_panel_rows(rows, schema_path)`：用标准库 jsonschema（若可用）
  或手工必填字段检查校验面板行；真实采集行若缺字段，必须标记为不完整，
  不得补填编造。

用法：
  python3 phase2b_t1.py --synthetic --out phase2b_t1_synthetic.json
  python3 phase2b_t1.py --panel phase2b_panel_rows.json --out phase2b_t1_real.json
全部合成数据除非另有逐行来源标注。
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def persistence_accuracy(rows):
    """rows 按 week_start 排序；预测下周方向 = 本周方向。返回 (准确率, 样本数,
    非发布周准确率, 非发布周样本数)。发布周定义：本周 model_release_count > 0
    （该周的热度不可外推，见 F2）。"""
    rows = sorted(rows, key=lambda r: r["week_start"])
    correct, n, correct_np, n_np = 0, 0, 0, 0
    for a, b in zip(rows, rows[1:]):
        pred = a["openrouter_share_direction"]
        ok = pred == b["openrouter_share_direction"]
        correct += ok; n += 1
        if a.get("model_release_count", 0) == 0:
            correct_np += ok; n_np += 1
    return {
        "persistence_accuracy": correct / n if n else None,
        "n_pairs": n,
        "persistence_accuracy_non_release_weeks": correct_np / n_np if n_np else None,
        "n_non_release_pairs": n_np,
    }


def majority_accuracy(rows):
    rows = sorted(rows, key=lambda r: r["week_start"])
    if len(rows) < 2:
        return {"majority_accuracy": None, "n_pairs": 0, "majority_class": None}
    from collections import Counter
    train = rows[:-1]
    maj = Counter(r["openrouter_share_direction"] for r in train).most_common(1)[0][0]
    correct = sum(1 for r in rows[1:] if r["openrouter_share_direction"] == maj)
    return {"majority_accuracy": correct / (len(rows) - 1), "n_pairs": len(rows) - 1,
            "majority_class": maj}


def synthetic_panel(n_weeks: int, seed: int, persistence: float = 0.8):
    """方向马尔可夫链：以概率 persistence 保持上周方向，否则均匀换到另两类。
    其余字段按 schema 填合成占位值，并标注 SYNTHETIC。"""
    import datetime
    rng = random.Random(seed)
    dirs = ["up", "flat", "down"]
    cur = rng.choice(dirs)
    start = datetime.date(2026, 1, 5)  # 周一
    rows = []
    for w in range(n_weeks):
        rows.append({
            "panel_id": "gtm-panel-v0", "week_start": str(start + datetime.timedelta(days=7 * w)),
            "segment": "developer_api", "cohort": "SYNTHETIC-MODEL-FAMILY",
            "model_release_count": 1 if w % 8 == 0 else 0,
            "license_type": "open_weights_with_custom_terms",
            "list_price_snapshot": {"off_peak_per_million": 0.14, "peak_per_million": 0.28,
                                    "cache_note": "synthetic"},
            "cloud_listings": 3, "third_party_hosts": 6, "host_price_spread": 2.4,
            "openrouter_share_direction": cur, "hf_downloads_band": "mid",
            "public_integrations": 12, "docs_examples_update_count": 2,
            "org_event_count": 0, "public_job_postings": 0, "controversy_event": False,
            "notes": "SYNTHETIC PANEL ROW — for baseline code test only",
        })
        if rng.random() < persistence:
            pass
        else:
            cur = rng.choice([d for d in dirs if d != cur])
    return rows


def validate_rows(rows):
    """手工必填字段检查（不依赖第三方库）：缺字段或枚举非法即不完整。"""
    required = ["panel_id", "week_start", "segment", "cohort", "model_release_count",
                "license_type", "cloud_listings", "third_party_hosts", "host_price_spread",
                "openrouter_share_direction", "hf_downloads_band", "public_integrations",
                "docs_examples_update_count", "org_event_count", "public_job_postings",
                "controversy_event"]
    bad = []
    for i, r in enumerate(rows):
        missing = [f for f in required if f not in r]
        if missing:
            bad.append({"row": i, "missing": missing})
        elif r["openrouter_share_direction"] not in ("up", "flat", "down"):
            bad.append({"row": i, "bad_direction": r["openrouter_share_direction"]})
    return {"n_rows": len(rows), "n_invalid": len(bad), "invalid": bad}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--panel", default=None)
    ap.add_argument("--out", default="phase2b_t1_synthetic.json")
    args = ap.parse_args()
    if args.synthetic:
        out = {}
        for p in [0.8, 1 / 3]:
            rows = synthetic_panel(52, seed=7, persistence=p)
            out[f"persistence_{p:.3f}"] = {
                "persistence_baseline": persistence_accuracy(rows),
                "majority_baseline": majority_accuracy(rows),
                "validation": validate_rows(rows),
            }
        Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(out, indent=2, ensure_ascii=False))
    elif args.panel:
        rows = json.loads(Path(args.panel).read_text(encoding="utf-8"))
        out = {"persistence_baseline": persistence_accuracy(rows),
               "majority_baseline": majority_accuracy(rows),
               "validation": validate_rows(rows)}
        Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        raise SystemExit("need --synthetic or --panel")


if __name__ == "__main__":
    main()
