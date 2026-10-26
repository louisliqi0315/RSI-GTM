"""Phase 2d 运行入口：先冒烟（小规模），再全量（1000 账户 / 10 种子）。"""
import argparse, json, math, statistics, sys
sys.path.insert(0, ".")
from phase2d_sim import run_arm, run_absorbing


def mean_ci(xs):
    n = len(xs)
    m = statistics.mean(xs)
    if n < 2:
        return m, 0.0
    sd = statistics.stdev(xs)
    # 95% t 区间半宽，n=10 时 t~2.262；用正态近似 1.96 会低估，显式用 t 值表
    t = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262}.get(n, 2.0)
    return m, t * sd / math.sqrt(n)


def paired_diff(a, b):
    xs = [x - y for x, y in zip(a, b)]
    m, hw = mean_ci(xs)
    wins = sum(1 for x in xs if x > 0)
    return {"mean": m, "ci95": [m - hw, m + hw], "halfwidth": hw, "wins": f"{wins}/{len(xs)}", "diffs": xs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="phase2d_results.json")
    ap.add_argument("--accounts", type=int, default=1000)
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--weeks", type=int, default=24)
    args = ap.parse_args()
    seeds = list(range(args.seeds))
    arms = {}
    per_seed = {}
    for arm in ("B", "C", "D", "E"):
        rows = []
        for s in seeds:
            r = run_arm(arm, s, args.accounts, args.weeks)
            rows.append(r)
            print(f"arm {arm} seed {s}: true={r['pipeline_per_trust']:.4f} claimed={r['claimed_pipeline_per_trust']:.4f} "
                  f"gap={r['separation_gap']:.4f} fake={r['fake_adoptions']}/{r['epochs_evaluated']} vetoes={r['vetoes']} "
                  f"harm_unsub={r['unsubscribe_rate_per_100_touches']:.3f} rep={r['mean_reputation_change']:.3f} empty={r['empty_comparison']}", flush=True)
        per_seed[arm] = rows
        for key in ("pipeline_per_trust", "claimed_pipeline_per_trust", "separation_gap",
                    "unsubscribe_rate_per_100_touches", "complaint_rate_per_100_touches",
                    "mean_reputation_change", "pipeline"):
            m, hw = mean_ci([r[key] for r in rows])
            arms.setdefault(arm, {})[key] = {"mean": m, "ci95": [m - hw, m + hw]}
        arms[arm]["fake_adoptions_total"] = sum(r["fake_adoptions"] for r in rows)
        arms[arm]["fake_adoptions_per_seed_mean"] = statistics.mean([r["fake_adoptions"] for r in rows])
        arms[arm]["adoptions_total"] = sum(r["adoptions"] for r in rows)
        arms[arm]["vetoes_total"] = sum(r["vetoes"] for r in rows)
        arms[arm]["empty_seeds"] = sum(1 for r in rows if r["empty_comparison"])
        arms[arm]["gate_changed_total"] = sum(r["gate_changed"] for r in rows)
    paired = {}
    for name, a, b in [("B-C", "B", "C"), ("B-D", "B", "D"), ("B-E", "B", "E"), ("D-C", "D", "C")]:
        paired[name] = {
            "true_pipeline_per_trust": paired_diff([r["pipeline_per_trust"] for r in per_seed[a]],
                                                   [r["pipeline_per_trust"] for r in per_seed[b]]),
            "separation_gap": paired_diff([r["separation_gap"] for r in per_seed[a]],
                                          [r["separation_gap"] for r in per_seed[b]]),
        }
    absorbing_rows = [run_absorbing(s) for s in seeds]
    absorbing = {}
    for key in ("hard_drop_reply_rate", "positive_gain_reply_rate", "spillover_drop_reply_rate",
                "absorbed_post_reply_ratio_to_control", "spillover_post_reply_ratio_to_control"):
        m, hw = mean_ci([r[key] for r in absorbing_rows])
        absorbing[key] = {"mean": m, "ci95": [m - hw, m + hw], "values": [r[key] for r in absorbing_rows]}
    absorbing["control_post_reply_mean"] = statistics.mean([r["control"]["post_reply_rate"] for r in absorbing_rows])
    absorbing["absorbed_post_reply_mean"] = statistics.mean([r["absorbed"]["post_reply_rate"] for r in absorbing_rows])
    absorbing["spillover_post_reply_mean"] = statistics.mean([r["spillover"]["post_reply_rate"] for r in absorbing_rows])
    out = {"config": {"accounts": args.accounts, "seeds": seeds, "weeks": args.weeks},
           "arms": arms, "paired": paired, "absorbing": absorbing,
           "per_seed": {a: [{k: r[k] for k in ("pipeline_per_trust", "claimed_pipeline_per_trust", "separation_gap",
                                                "fake_adoptions", "adoptions", "vetoes", "empty_comparison",
                                                "unsubscribe_rate_per_100_touches", "complaint_rate_per_100_touches",
                                                "mean_reputation_change", "final_config")} for r in rows]
                        for a, rows in per_seed.items()}}
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("WROTE", args.out)


if __name__ == "__main__":
    main()
