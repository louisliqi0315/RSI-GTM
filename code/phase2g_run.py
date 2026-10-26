"""Phase 2g 运行入口：工作流-only 有门 vs 静态 G，1000 账户 / 30 种子 / 24 周。

统计：配对差 95% t 区间。主结论用全部 30 种子（含空比较种子）；
敏感性单独报剔除空比较种子（W 空比较）后的配对差，仅作披露。
t 临界值：df=29 时 2.045；敏感性子样本按 df 查表（df>=30 时用 2.0 近似，
仅用于披露，不影响主判定）。
"""
import argparse
import json
import math
import statistics
import sys

sys.path.insert(0, ".")
from phase2g_sim import run_arm_f

T_TABLE = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 15: 2.131, 20: 2.086, 25: 2.060, 29: 2.045,
}


def t_crit(df):
    if df in T_TABLE:
        return T_TABLE[df]
    # 最近的较小 df 对应的临界值（保守），df>29 时 2.045 已接近 2.0
    lower = max([d for d in T_TABLE if d < df], default=29)
    return T_TABLE[lower]


def mean_ci(xs):
    n = len(xs)
    m = statistics.mean(xs)
    if n < 2:
        return m, 0.0, 0.0
    sd = statistics.stdev(xs)
    hw = t_crit(n - 1) * sd / math.sqrt(n)
    return m, m - hw, m + hw


def paired(xs_a, xs_b):
    diffs = [a - b for a, b in zip(xs_a, xs_b)]
    m, lo, hi = mean_ci(diffs)
    return {
        "mean": m, "ci95": [lo, hi],
        "wins": sum(1 for d in diffs if d > 0),
        "losses": sum(1 for d in diffs if d < 0),
        "ties": sum(1 for d in diffs if d == 0),
        "n": len(diffs), "diffs": diffs,
    }


def summarize(rows):
    out = {}
    for key in ("pipeline_per_trust", "claimed_pipeline_per_trust", "separation_gap",
                "unsubscribe_rate_per_100_touches", "complaint_rate_per_100_touches",
                "mean_reputation_change", "pipeline", "trust_consumed", "wait_share"):
        m, lo, hi = mean_ci([r[key] for r in rows])
        out[key] = {"mean": m, "ci95": [lo, hi]}
    out["fake_adoptions_total"] = sum(r["fake_adoptions"] for r in rows)
    out["adoptions_total"] = sum(r["adoptions"] for r in rows)
    out["vetoes_total"] = sum(r["vetoes"] for r in rows)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="phase2g_results.json")
    ap.add_argument("--accounts", type=int, default=1000)
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--weeks", type=int, default=24)
    args = ap.parse_args()
    seeds = list(range(args.seeds))
    per_seed = {}
    for arm in ("W", "STATIC"):
        rows = []
        for s in seeds:
            r = run_arm_f(arm, s, args.accounts, args.weeks)
            rows.append(r)
            print(f"arm {arm} seed {s}: true={r['pipeline_per_trust']:.4f} "
                  f"adopt={r['adoptions']} vetoes={r['vetoes']} fake={r['fake_adoptions']} "
                  f"unsub={r['unsubscribe_rate_per_100_touches']:.3f} "
                  f"rep={r['mean_reputation_change']:.3f} empty={r['empty_comparison']}",
                  flush=True)
        per_seed[arm] = rows
    empty_w = [s for s, r in zip(seeds, per_seed["W"]) if r["empty_comparison"]]
    main_paired = paired(
        [r["pipeline_per_trust"] for r in per_seed["W"]],
        [r["pipeline_per_trust"] for r in per_seed["STATIC"]],
    )
    # 敏感性：仅剔除 W 空比较种子（此时 W 与 STATIC 差恒为 0 的种子）
    keep = [i for i, r in enumerate(per_seed["W"]) if not r["empty_comparison"]]
    sens = paired(
        [per_seed["W"][i]["pipeline_per_trust"] for i in keep],
        [per_seed["STATIC"][i]["pipeline_per_trust"] for i in keep],
    ) if keep else None
    # 一致性锚点：W 空比较种子上 W 与 STATIC 真值必须完全相等
    anchor_ok = all(
        per_seed["W"][i]["pipeline_per_trust"] == per_seed["STATIC"][i]["pipeline_per_trust"]
        for i, s in enumerate(seeds) if s in empty_w
    )
    harm = {
        "unsubscribe_rate_per_100_touches": paired(
            [r["unsubscribe_rate_per_100_touches"] for r in per_seed["W"]],
            [r["unsubscribe_rate_per_100_touches"] for r in per_seed["STATIC"]]),
        "mean_reputation_change": paired(
            [r["mean_reputation_change"] for r in per_seed["W"]],
            [r["mean_reputation_change"] for r in per_seed["STATIC"]]),
        "complaint_rate_per_100_touches": paired(
            [r["complaint_rate_per_100_touches"] for r in per_seed["W"]],
            [r["complaint_rate_per_100_touches"] for r in per_seed["STATIC"]]),
    }
    out = {
        "config": {"accounts": args.accounts, "seeds": seeds, "weeks": args.weeks,
                   "note": "W and STATIC from phase2f_sim.run_arm_f via phase2g_sim (identical to 2f); no parameter changes."},
        "arms": {a: summarize(rows) for a, rows in per_seed.items()},
        "empty_seeds_W": empty_w,
        "empty_seed_count_W": len(empty_w),
        "anchor_empty_seeds_equal": anchor_ok,
        "paired_W_minus_STATIC": main_paired,
        "sensitivity_excluding_empty_W": sens,
        "sensitivity_kept_seeds": [seeds[i] for i in keep],
        "paired_harm": harm,
        "per_seed": {a: [{k: r[k] for k in ("pipeline_per_trust", "claimed_pipeline_per_trust",
                                             "separation_gap", "fake_adoptions", "adoptions", "vetoes",
                                             "empty_comparison", "unsubscribe_rate_per_100_touches",
                                             "complaint_rate_per_100_touches", "mean_reputation_change",
                                             "pipeline", "trust_consumed", "wait_share", "final_config")}
                        for r in rows] for a, rows in per_seed.items()},
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("WROTE", args.out, "anchor_ok=", anchor_ok)


if __name__ == "__main__":
    main()
