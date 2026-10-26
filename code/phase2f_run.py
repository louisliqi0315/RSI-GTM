"""Phase 2f 运行入口：先冒烟（小规模），再全量（1000 账户 / 10 种子 / 24 周）。

臂：STATIC / W / S（phase2f_sim.run_arm_f）+ B / C / D（phase2d_sim.run_arm
同批种子重跑，不挪用 phase2d_results.json 的数字）。同一批种子配对比较。
"""
import argparse, json, math, statistics, sys
sys.path.insert(0, ".")
from phase2f_sim import run_arm_f
from phase2d_sim import run_arm


def mean_ci(xs):
    n = len(xs)
    m = statistics.mean(xs)
    if n < 2:
        return m, 0.0
    sd = statistics.stdev(xs)
    t = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262}.get(n, 2.0)
    return m, t * sd / math.sqrt(n)


def paired_diff(a, b):
    xs = [x - y for x, y in zip(a, b)]
    m, hw = mean_ci(xs)
    wins = sum(1 for x in xs if x > 0)
    losses = sum(1 for x in xs if x < 0)
    ties = sum(1 for x in xs if x == 0)
    return {"mean": m, "ci95": [m - hw, m + hw], "halfwidth": hw,
            "wins": f"{wins}/{len(xs)}", "losses": losses, "ties": ties, "diffs": xs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="phase2f_results.json")
    ap.add_argument("--accounts", type=int, default=1000)
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--weeks", type=int, default=24)
    args = ap.parse_args()
    seeds = list(range(args.seeds))
    arms = {}
    per_seed = {}
    for arm in ("STATIC", "W", "S", "B", "C", "D"):
        rows = []
        for s in seeds:
            r = run_arm_f(arm, s, args.accounts, args.weeks) if arm in ("STATIC", "W", "S") else run_arm(arm, s, args.accounts, args.weeks)
            rows.append(r)
            print(f"arm {arm} seed {s}: true={r['pipeline_per_trust']:.4f} claimed={r['claimed_pipeline_per_trust']:.4f} "
                  f"gap={r['separation_gap']:.4f} fake={r['fake_adoptions']}/{r['epochs_evaluated']} adopt={r['adoptions']} "
                  f"vetoes={r['vetoes']} harm_unsub={r['unsubscribe_rate_per_100_touches']:.3f} rep={r['mean_reputation_change']:.3f} "
                  f"empty={r['empty_comparison']} final={r['final_config']}", flush=True)
        per_seed[arm] = rows
        for key in ("pipeline_per_trust", "claimed_pipeline_per_trust", "separation_gap",
                    "unsubscribe_rate_per_100_touches", "complaint_rate_per_100_touches",
                    "mean_reputation_change", "pipeline", "trust_consumed", "wait_share"):
            m, hw = mean_ci([r[key] for r in rows])
            arms.setdefault(arm, {})[key] = {"mean": m, "ci95": [m - hw, m + hw]}
        arms[arm]["fake_adoptions_total"] = sum(r["fake_adoptions"] for r in rows)
        arms[arm]["adoptions_total"] = sum(r["adoptions"] for r in rows)
        arms[arm]["vetoes_total"] = sum(r["vetoes"] for r in rows)
        arms[arm]["empty_seeds"] = [s for s, r in zip(seeds, rows) if r["empty_comparison"]]
        arms[arm]["empty_seed_count"] = len(arms[arm]["empty_seeds"])
    paired = {}
    for name, a, b in [("B-STATIC", "B", "STATIC"), ("W-STATIC", "W", "STATIC"),
                       ("S-STATIC", "S", "STATIC"), ("B-W", "B", "W"), ("B-S", "B", "S"),
                       ("B-C", "B", "C"), ("B-D", "B", "D"), ("W-S", "W", "S")]:
        paired[name] = {
            "true_pipeline_per_trust": paired_diff([r["pipeline_per_trust"] for r in per_seed[a]],
                                                   [r["pipeline_per_trust"] for r in per_seed[b]]),
            "separation_gap": paired_diff([r["separation_gap"] for r in per_seed[a]],
                                          [r["separation_gap"] for r in per_seed[b]]),
            "mean_reputation_change": paired_diff([r["mean_reputation_change"] for r in per_seed[a]],
                                                  [r["mean_reputation_change"] for r in per_seed[b]]),
        }
    # 排名翻转：宣称高于 B 但真值低于 B 的种子数（C/D 臂）
    flips = {}
    for arm in ("C", "D"):
        flips[arm] = sum(1 for rb, ra in zip(per_seed["B"], per_seed[arm])
                         if ra["claimed_pipeline_per_trust"] > rb["claimed_pipeline_per_trust"]
                         and ra["pipeline_per_trust"] < rb["pipeline_per_trust"])
    out = {"config": {"accounts": args.accounts, "seeds": seeds, "weeks": args.weeks,
                      "note": "B/C/D rerun in this batch with same seeds (not copied from phase2d_results.json); "
                              "STATIC/W/S from phase2f_sim on phase2d_sim lineage."},
           "arms": arms, "paired": paired, "rank_flips_vs_B": flips,
           "per_seed": {a: [{k: r[k] for k in ("pipeline_per_trust", "claimed_pipeline_per_trust", "separation_gap",
                                                "fake_adoptions", "adoptions", "vetoes", "empty_comparison",
                                                "unsubscribe_rate_per_100_touches", "complaint_rate_per_100_touches",
                                                "mean_reputation_change", "pipeline", "trust_consumed", "wait_share",
                                                "final_config")} for r in rows]
                        for a, rows in per_seed.items()}}
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("WROTE", args.out)


if __name__ == "__main__":
    main()
