"""Phase 2j 运行入口：STATIC / A0（复现 2i-A）/ C（严格超集 8 候选）/
D（每 epoch 独立验证种子），1000 账户 / 30 种子 / 48 周 / 8 周 epoch。

统计：配对差 95% t 区间。主结论用全部 30 种子（含空比较种子）；
敏感性单独报剔除空比较种子后的配对差，仅作披露。
t 临界值：df=29 时 2.045；敏感性子样本按 df 查表。
逐轮次曲线：以各段快照（第 8、16、…、48 周累计真值管道/信任）计算
同周配对差，仅作趋势披露；主判定只看 48 周终点。
C 与 D 的比较只作各自是否打破深度 1 的并列陈述，C−D 配对差仅作
描述性数字，不得据此判机制更优。
"""
import argparse
import json
import math
import statistics
import sys
from collections import Counter

sys.path.insert(0, ".")
from phase2j_sim import run_arm_j, _candidates_strict_superset, _validation_seeds
from phase2f_sim import BASE_CFG

T_TABLE = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 15: 2.131, 20: 2.086, 25: 2.060, 29: 2.045,
}


def t_crit(df):
    if df in T_TABLE:
        return T_TABLE[df]
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
    out["progressive_adoptions_total"] = sum(r["progressive_adoptions"] for r in rows)
    out["vetoes_total"] = sum(r["vetoes"] for r in rows)
    out["adoption_depth_distribution"] = dict(Counter(r["adoptions"] for r in rows))
    out["seeds_with_ge2_adoptions"] = sum(1 for r in rows if r["adoptions"] >= 2)
    out["seeds_with_progressive_adoption"] = sum(1 for r in rows if r["progressive_adoptions"] >= 1)
    out["final_workflow_distribution"] = dict(Counter(r["final_config"]["workflow"] for r in rows))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="phase2j_results.json")
    ap.add_argument("--accounts", type=int, default=1000)
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--weeks", type=int, default=48)
    ap.add_argument("--epoch", type=int, default=8)
    args = ap.parse_args()
    seeds = list(range(args.seeds))
    # 冒烟前置断言（全量入口内亦执行，失败即退出，不出结果文件）：
    assert len(_candidates_strict_superset(dict(BASE_CFG))) == 8, "C candidate count != 8"
    assert any(c["threshold"] == BASE_CFG["threshold"] and c["lambda"] == 2.0
               for c in _candidates_strict_superset(dict(BASE_CFG))), \
        "C missing thr-unchanged lam-1 variant"
    d_seeds = [_validation_seeds("D", 0, e) for e in range(1, 6)]
    assert len(set(d_seeds)) == 5, "D validation seeds not distinct per epoch"
    assert all(a != 0 and r != 0 for a, r in d_seeds), "D validation seed conflicts with main seed"
    per_seed = {}
    for arm in ("STATIC", "A0", "C", "D"):
        rows = []
        for s in seeds:
            r = run_arm_j(arm, s, args.accounts, args.weeks, args.epoch)
            rows.append(r)
            print(f"arm {arm} seed {s}: true={r['pipeline_per_trust']:.4f} "
                  f"adopt={r['adoptions']} prog={r['progressive_adoptions']} "
                  f"wf={r['adoption_workflows']} vetoes={r['vetoes']} fake={r['fake_adoptions']} "
                  f"unsub={r['unsubscribe_rate_per_100_touches']:.3f} "
                  f"rep={r['mean_reputation_change']:.3f} empty={r['empty_comparison']}",
                  flush=True)
        per_seed[arm] = rows
    empty = {arm: [s for s, r in zip(seeds, per_seed[arm]) if r["empty_comparison"]]
             for arm in ("A0", "C", "D")}
    anchor_ok = {
        arm: all(per_seed[arm][i]["pipeline_per_trust"] == per_seed["STATIC"][i]["pipeline_per_trust"]
                 for i, s in enumerate(seeds) if s in empty[arm])
        for arm in ("A0", "C", "D")
    }
    def p(a, b):
        return paired([r["pipeline_per_trust"] for r in per_seed[a]],
                      [r["pipeline_per_trust"] for r in per_seed[b]])
    def sens(arm):
        keep = [i for i, r in enumerate(per_seed[arm]) if not r["empty_comparison"]]
        if not keep:
            return None
        return {"paired": paired([per_seed[arm][i]["pipeline_per_trust"] for i in keep],
                                 [per_seed["STATIC"][i]["pipeline_per_trust"] for i in keep]),
                "kept_seeds": [seeds[i] for i in keep]}
    weeks_list = [snap["week"] for snap in per_seed["A0"][0]["snapshots"]]
    eval_weeks = [w for w in weeks_list if w < args.weeks]
    per_week = {}
    for arm in ("A0", "C", "D"):
        per_week[arm] = []
        for wi, wk in enumerate(weeks_list):
            d = paired([r["snapshots"][wi]["pipeline_per_trust"] for r in per_seed[arm]],
                       [r["snapshots"][wi]["pipeline_per_trust"] for r in per_seed["STATIC"]])
            per_week[arm].append({"week": wk, **d})
    adopt_by_week = {
        arm: {w: sum(1 for r in per_seed[arm] if w in r["adoption_weeks"]) for w in eval_weeks}
        for arm in ("A0", "C", "D")
    }
    harm = {}
    for arm in ("A0", "C", "D"):
        harm[arm] = {
            k: paired([r[k] for r in per_seed[arm]], [r[k] for r in per_seed["STATIC"]])
            for k in ("unsubscribe_rate_per_100_touches", "mean_reputation_change",
                      "complaint_rate_per_100_touches")
        }
    out = {
        "config": {"accounts": args.accounts, "seeds": seeds, "weeks": args.weeks,
                   "epoch": args.epoch,
                   "note": "STATIC/A0/C/D from phase2j_sim.run_arm_j; gate, validation scale (200/8w), STATIC identical to 2i. A0: old binary candidate set (4), validation reused seed+1000/seed+2000 (replicates 2i-A). C: strict superset (4 tunes x 2 non-incumbent workflows = 8, incl. thr-unchanged lam-1), validation reused as A0; only candidate space vs A0 differs. D: same candidates as A0, validation seeds independent per epoch (seed+1000+e*10000 / seed+2000+e*10000); only validation-seed independence vs A0 differs."},
        "arms": {a: summarize(rows) for a, rows in per_seed.items()},
        "empty_seeds": empty,
        "empty_seed_counts": {a: len(v) for a, v in empty.items()},
        "empty_rates": {a: len(v) / len(seeds) for a, v in empty.items()},
        "anchor_empty_seeds_equal": anchor_ok,
        "paired_A0_minus_STATIC_48w": p("A0", "STATIC"),
        "paired_C_minus_STATIC_48w": p("C", "STATIC"),
        "paired_D_minus_STATIC_48w": p("D", "STATIC"),
        "paired_C_minus_A0_48w": p("C", "A0"),
        "paired_D_minus_A0_48w": p("D", "A0"),
        "paired_C_minus_D_48w_descriptive_only": p("C", "D"),
        "sensitivity_excluding_empty": {a: sens(a) for a in ("A0", "C", "D")},
        "paired_harm": harm,
        "per_week_paired": per_week,
        "adoptions_by_eval_week": adopt_by_week,
        "eval_weeks": eval_weeks,
        "per_seed": {a: [{k: r[k] for k in ("pipeline_per_trust", "claimed_pipeline_per_trust",
                                             "separation_gap", "fake_adoptions", "adoptions",
                                             "progressive_adoptions", "vetoes",
                                             "empty_comparison", "unsubscribe_rate_per_100_touches",
                                             "complaint_rate_per_100_touches", "mean_reputation_change",
                                             "pipeline", "trust_consumed", "wait_share", "final_config",
                                             "adoption_weeks", "adoption_workflows", "snapshots",
                                             "validation_seed_log")}
                        for r in rows] for a, rows in per_seed.items()},
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("WROTE", args.out, "anchor_ok=", anchor_ok)


if __name__ == "__main__":
    main()
