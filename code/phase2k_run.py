"""Phase 2k 运行入口：STATIC / D0（复现 2j-D）/ E（双样本门）/
F（回退），1000 账户 / 30 种子 / 48 周 / 8 周 epoch。

统计：配对差 95% t 区间。主结论用全部 30 种子（含空比较种子）；
敏感性单独报剔除空比较种子后的配对差，仅作披露。
t 临界值：df=29 时 2.045；敏感性子样本按 df 查表。
逐轮次曲线：以各段快照（第 8、16、…、48 周累计真值管道/信任）计算
同周配对差，仅作趋势披露；主判定只看 48 周终点。
E−F 配对差仅作描述性数字，不得据此判机制更优；F−D0 的空比较率与
深度分布比较是 F 判定的组成部分，按预注册 §2 操作化执行。
"""
import argparse
import json
import math
import statistics
import sys
from collections import Counter

sys.path.insert(0, ".")
from phase2k_sim import run_arm_k, _validation_seeds, _confirmation_seeds

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
    ap.add_argument("--out", default="phase2k_results.json")
    ap.add_argument("--accounts", type=int, default=1000)
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--weeks", type=int, default=48)
    ap.add_argument("--epoch", type=int, default=8)
    args = ap.parse_args()
    seeds = list(range(args.seeds))
    # 冒烟前置断言（全量入口内亦执行，失败即退出，不出结果文件）：
    d_seeds = [_validation_seeds("D0", 0, e) for e in range(1, 6)]
    assert len(set(d_seeds)) == 5, "D0 validation seeds not distinct per epoch"
    assert all(a != 0 and r != 0 for a, r in d_seeds), "D0 validation seed conflicts with main seed"
    for e in range(1, 6):
        a2, r2 = _confirmation_seeds(0, e)
        a1, r1 = _validation_seeds("D0", 0, e)
        assert (a2, r2) != (a1, r1), "E confirmation seed equals epoch seed"
        assert a2 != 0 and r2 != 0, "E confirmation seed conflicts with main seed"
    # 冒烟运行：50 账户 / 2 种子 / 16 周，各臂均能跑通且 D0 空比较锚点逻辑可检查。
    for arm in ("STATIC", "D0", "E", "F"):
        for s in (0, 1):
            r = run_arm_k(arm, s, 50, 16, 8)
            print(f"smoke arm {arm} seed {s}: true={r['pipeline_per_trust']:.4f} "
                  f"adopt={r['adoptions']} prog={r['progressive_adoptions']} "
                  f"details={r['adoption_details']}", flush=True)
    per_seed = {}
    for arm in ("STATIC", "D0", "E", "F"):
        rows = []
        for s in seeds:
            r = run_arm_k(arm, s, args.accounts, args.weeks, args.epoch)
            rows.append(r)
            print(f"arm {arm} seed {s}: true={r['pipeline_per_trust']:.4f} "
                  f"adopt={r['adoptions']} prog={r['progressive_adoptions']} "
                  f"wf={r['adoption_workflows']} vetoes={r['vetoes']} fake={r['fake_adoptions']} "
                  f"unsub={r['unsubscribe_rate_per_100_touches']:.3f} "
                  f"rep={r['mean_reputation_change']:.3f} empty={r['empty_comparison']} "
                  f"details={r['adoption_details']}", flush=True)
        per_seed[arm] = rows
    empty = {arm: [s for s, r in zip(seeds, per_seed[arm]) if r["empty_comparison"]]
             for arm in ("D0", "E", "F")}
    anchor_ok = {
        arm: all(per_seed[arm][i]["pipeline_per_trust"] == per_seed["STATIC"][i]["pipeline_per_trust"]
                 for i, s in enumerate(seeds) if s in empty[arm])
        for arm in ("D0", "E", "F")
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
    # D0 与 2j 臂 D 的逐种子复现检查（若 2j 结果文件存在）。
    d0_vs_2jD = None
    try:
        with open("phase2j_results.json") as f:
            j = json.load(f)
        jD = j["per_seed"]["D"]
        diffs = [abs(per_seed["D0"][i]["pipeline_per_trust"] - jD[i]["pipeline_per_trust"])
                 for i in range(len(seeds))]
        d0_vs_2jD = {"max_diff": max(diffs), "exact_equal_count": sum(1 for d in diffs if d == 0.0)}
    except Exception as exc:  # noqa: BLE001 - 仅用于复现检查缺失时的披露
        d0_vs_2jD = {"error": str(exc)}
    weeks_list = [snap["week"] for snap in per_seed["D0"][0]["snapshots"]]
    eval_weeks = [w for w in weeks_list if w < args.weeks]
    per_week = {}
    for arm in ("D0", "E", "F"):
        per_week[arm] = []
        for wi, wk in enumerate(weeks_list):
            d = paired([r["snapshots"][wi]["pipeline_per_trust"] for r in per_seed[arm]],
                       [r["snapshots"][wi]["pipeline_per_trust"] for r in per_seed["STATIC"]])
            per_week[arm].append({"week": wk, **d})
    adopt_by_week = {
        arm: {w: sum(1 for r in per_seed[arm] if w in r["adoption_weeks"]) for w in eval_weeks}
        for arm in ("D0", "E", "F")
    }
    harm = {}
    for arm in ("D0", "E", "F"):
        harm[arm] = {
            k: paired([r[k] for r in per_seed[arm]], [r[k] for r in per_seed["STATIC"]])
            for k in ("unsubscribe_rate_per_100_touches", "mean_reputation_change",
                      "complaint_rate_per_100_touches")
        }
    # 干净检验案例：种子 6、29 在 D0/E/F 中的逐一种子结果。
    case_seeds = {}
    for s in (6, 29):
        i = seeds.index(s)
        case_seeds[str(s)] = {
            arm: {"pipeline_per_trust": per_seed[arm][i]["pipeline_per_trust"],
                  "adoptions": per_seed[arm][i]["adoptions"],
                  "progressive_adoptions": per_seed[arm][i]["progressive_adoptions"],
                  "adoption_details": per_seed[arm][i]["adoption_details"],
                  "vetoes": per_seed[arm][i]["vetoes"],
                  "veto_log": per_seed[arm][i]["veto_log"],
                  "final_config": per_seed[arm][i]["final_config"],
                  "empty_comparison": per_seed[arm][i]["empty_comparison"]}
            for arm in ("STATIC", "D0", "E", "F")
        }
        case_seeds[str(s)]["paired_vs_STATIC"] = {
            arm: per_seed[arm][i]["pipeline_per_trust"] - per_seed["STATIC"][i]["pipeline_per_trust"]
            for arm in ("D0", "E", "F")
        }
    # F 回退采纳统计：rank>0 的采纳次数与种子。
    fallback_stats = {}
    for arm in ("D0", "E", "F"):
        fb = [(seeds[i], d) for i, r in enumerate(per_seed[arm]) for d in r["adoption_details"]
              if d["fallback_used"]]
        fallback_stats[arm] = {"count": len(fb), "seed_details": fb}
    out = {
        "config": {"accounts": args.accounts, "seeds": seeds, "weeks": args.weeks,
                   "epoch": args.epoch,
                   "note": "STATIC/D0/E/F from phase2k_sim.run_arm_k; gate, validation scale (200/8w), STATIC identical to 2j. D0: replicates 2j-D (independent validation seeds seed+1000+e*10000 / seed+2000+e*10000, old binary 4 candidates, winner-take-all). E: only change vs D0 is dual-sample confirmation (second sample seeds +5000 each, same gate, no fallback). F: only change vs D0 is fallback rule (first passing candidate in validation order, else veto)."},
        "arms": {a: summarize(rows) for a, rows in per_seed.items()},
        "empty_seeds": empty,
        "empty_seed_counts": {a: len(v) for a, v in empty.items()},
        "empty_rates": {a: len(v) / len(seeds) for a, v in empty.items()},
        "anchor_empty_seeds_equal": anchor_ok,
        "d0_vs_2jD": d0_vs_2jD,
        "paired_D0_minus_STATIC_48w": p("D0", "STATIC"),
        "paired_E_minus_STATIC_48w": p("E", "STATIC"),
        "paired_F_minus_STATIC_48w": p("F", "STATIC"),
        "paired_E_minus_D0_48w": p("E", "D0"),
        "paired_F_minus_D0_48w": p("F", "D0"),
        "paired_E_minus_F_48w_descriptive_only": p("E", "F"),
        "sensitivity_excluding_empty": {a: sens(a) for a in ("D0", "E", "F")},
        "paired_harm": harm,
        "per_week_paired": per_week,
        "adoptions_by_eval_week": adopt_by_week,
        "eval_weeks": eval_weeks,
        "case_seeds_6_29": case_seeds,
        "fallback_stats": fallback_stats,
        "per_seed": {a: [{k: r[k] for k in ("pipeline_per_trust", "claimed_pipeline_per_trust",
                                             "separation_gap", "fake_adoptions", "adoptions",
                                             "progressive_adoptions", "vetoes",
                                             "empty_comparison", "unsubscribe_rate_per_100_touches",
                                             "complaint_rate_per_100_touches", "mean_reputation_change",
                                             "pipeline", "trust_consumed", "wait_share", "final_config",
                                             "adoption_weeks", "adoption_workflows", "adoption_details",
                                             "snapshots", "validation_seed_log", "veto_log")}
                        for r in rows] for a, rows in per_seed.items()},
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("WROTE", args.out, "anchor_ok=", anchor_ok, "d0_vs_2jD=", d0_vs_2jD)


if __name__ == "__main__":
    main()
