"""
Phase 2j — 严格超集复测（C）与独立验证种子检验（D），48 周 / 8 周 epoch
（新文件，不改动 gtm_sim.py / phase2d_* / phase2f_* / phase2g_* / phase2h_* /
phase2i_* / 任何论文稿）

合成数据声明：全部机制均为合成假设，不是真实厂商数据，不宣称真实
转化率、收入、厂商表现或跨厂商泛化。

与 2i 同口径（仅预注册改动）：
- 同一门容忍（退订 +0.2、投诉 +0.1、信任上限 1.10 倍、wait_share < 0.95、
  真值 > 现任）、同一验证集规模（200 账户 / 8 周）、同一主指标
  （冻结评估器 pipeline_per_trust）、同一假采纳定义、同一伤害指标、
  同一静态 G（全程固定 {W0, S0, threshold 0.40, lambda 3.0}）。
- 对照臂 A0：复现 2i 臂 A（旧二元候选集 _candidates_w_only，共 4 候选；
  验证集各 epoch 复用账户种子 seed+1000、运行种子 seed+2000）。
- 臂 C：与 A0 的唯一差别是候选空间补齐——每工作流 4 变体 × 2 个
  非现任工作流（W1、W2）= 8 候选，含“thr 不变、lam−1”变体；
  验证集复用方式与 A0 完全相同。主运行与验证集均用 policy_i
  （policy_i 对 W0/W1 与 policy_d 逐行一致，见 phase2i_sim）。
- 臂 D：与 A0 的唯一差别是验证集——每 epoch 用独立验证种子：
  第 e 次评估（e=1..5）时账户种子 = seed+1000+e*10000、
  运行种子 = seed+2000+e*10000；候选集与 A0 完全相同
  （旧二元、4 变体），主运行与验证集均用原 policy_d，
  验证集规模与时程、门容忍全部不变。
- 快照不消耗随机数：finalize_metrics 为纯计算，不触碰 rng，
  故逐段快照不改变账户轨迹；空比较种子上各臂与 STATIC 仍须
  逐种子完全相等。
"""
from __future__ import annotations

import random
from typing import Dict, List

from gtm_sim import (
    make_accounts, evolve_account, apply_action, finalize_metrics, new_metrics,
)
from phase2d_sim import policy_d, run_policy, _gate_pass, _legal
from phase2f_sim import _candidates_w_only, BASE_CFG
from phase2i_sim import policy_i, run_policy_i

WEEKS_J = 48
EPOCH_J = 8
WORKFLOWS = ["W0", "W1", "W2"]


def _candidates_strict_superset(cfg: Dict) -> List[Dict]:
    """C 臂候选集：2 个非现任工作流 × 4 种阈值/λ组合，共 8 个。状态恒 S0。

    4 种组合与 _candidates_w_only 完全一致：
    (基线 thr/lam)、(thr+0.05 上限 0.8, lam)、(thr−0.05 下限 0.15, lam−1 下限 1.0)、
    (thr 不变, lam−1 下限 1.0)——最后一项即 2i 臂 B 缺少的变体。
    """
    cur = cfg.get("workflow", "W0")
    others = [w for w in WORKFLOWS if w != cur]
    thr = cfg.get("threshold", 0.40)
    lam = cfg.get("lambda", 3.0)
    tunes = [
        (thr, lam),
        (min(0.8, thr + 0.05), lam),
        (max(0.15, thr - 0.05), max(1.0, lam - 1.0)),
        (thr, max(1.0, lam - 1.0)),
    ]
    return [
        {"workflow": w, "state": "S0", "threshold": t, "lambda": l}
        for w in others for (t, l) in tunes
    ]


def _validation_seeds(arm: str, seed: int, epoch_idx: int):
    """返回 (账户种子, 运行种子)。A0/C 各 epoch 复用；D 每 epoch 独立。

    epoch_idx 为第几次评估（1..5）。D：账户种子 seed+1000+e*10000，
    运行种子 seed+2000+e*10000；与主运行种子（seed）及 A0/C 的
    验证种子（seed+1000、seed+2000）均不冲突。
    """
    if arm == "D":
        return seed + 1000 + epoch_idx * 10000, seed + 2000 + epoch_idx * 10000
    return seed + 1000, seed + 2000


def _snapshot(metrics: Dict, accounts) -> Dict:
    fm = finalize_metrics(metrics, accounts)
    return {
        "pipeline_per_trust": fm["pipeline_per_trust"],
        "pipeline": fm["pipeline"],
        "trust_consumed": fm["trust_consumed"],
        "unsubscribe_rate_per_100_touches": fm["unsubscribe_rate_per_100_touches"],
        "complaint_rate_per_100_touches": fm["complaint_rate_per_100_touches"],
        "mean_reputation_change": fm["mean_reputation_change"],
        "wait_share": fm["wait_share"],
    }


def run_arm_j(arm: str, seed: int, n_accounts: int, weeks: int = WEEKS_J,
              epoch: int = EPOCH_J) -> Dict:
    """跑一 2j 臂。arm in {STATIC, A0, C, D}。主运行循环逐行对齐 phase2i_sim.run_arm_i。"""
    assert arm in ("STATIC", "A0", "C", "D")
    cfg: Dict = dict(BASE_CFG)
    rng = random.Random(seed)
    accounts = make_accounts(n_accounts, seed)
    metrics = new_metrics()
    veto_log: List[Dict] = []
    fake_adoptions = 0
    adoptions = 0
    progressive_adoptions = 0
    prev_workflow_before_last_adoption = None
    epochs_evaluated = 0
    adoption_weeks: List[int] = []
    adoption_workflows: List[str] = []
    snapshots: List[Dict] = []
    # D 臂验证种子审计：记录各 epoch 实际使用的 (账户种子, 运行种子)
    validation_seed_log: List[Dict] = []
    for start in range(0, weeks, epoch):
        epoch_weeks = min(epoch, weeks - start)
        for _ in range(epoch_weeks):
            for acct in accounts:
                evolve_account(acct, rng)
                obs = acct.observed_intent(rng)
                if arm == "C":
                    action = _legal(acct, policy_i(acct, obs, cfg, rng))
                else:
                    action = _legal(acct, policy_d(acct, obs, cfg, rng))
                apply_action(acct, action, rng, metrics)
        snap = _snapshot(metrics, accounts)
        snap["week"] = start + epoch_weeks
        snapshots.append(snap)
        if start + epoch_weeks >= weeks:
            break
        if arm == "STATIC":
            continue
        # ---- 递归候选评估（验证集规模 200 / 8 周，种子规则见 _validation_seeds）----
        epochs_evaluated += 1
        acct_seed, run_seed = _validation_seeds(arm, seed, epochs_evaluated)
        validation_seed_log.append({"epoch": epochs_evaluated, "week": start + epoch_weeks,
                                    "account_seed": acct_seed, "run_seed": run_seed})
        if arm == "C":
            incumbent_val = run_policy_i(make_accounts(200, acct_seed), cfg, 8, run_seed)
            cands = _candidates_strict_superset(cfg)
            cand_true = [run_policy_i(make_accounts(200, acct_seed), c, 8, run_seed)
                         for c in cands]
        else:
            incumbent_val = run_policy(make_accounts(200, acct_seed), cfg, 8, run_seed)
            cands = _candidates_w_only(cfg)
            cand_true = [run_policy(make_accounts(200, acct_seed), c, 8, run_seed)
                         for c in cands]
        best_idx = max(range(len(cands)), key=lambda i: cand_true[i]["pipeline_per_trust"])
        if _gate_pass(cand_true[best_idx], incumbent_val, 0.2, 0.1, 1.10):
            chosen = best_idx
        else:
            veto_log.append({"epoch": epochs_evaluated, "week": start + epoch_weeks,
                             "reason": "gate_failed",
                             "best_true": cand_true[best_idx]["pipeline_per_trust"],
                             "incumbent_true": incumbent_val["pipeline_per_trust"]})
            chosen = None
        if chosen is not None:
            old_wf = cfg.get("workflow", "W0")
            new_wf = cands[chosen]["workflow"]
            if prev_workflow_before_last_adoption is not None \
                    and new_wf != prev_workflow_before_last_adoption:
                progressive_adoptions += 1
            prev_workflow_before_last_adoption = old_wf
            adoptions += 1
            adoption_weeks.append(start + epoch_weeks)
            adoption_workflows.append(new_wf)
            if cand_true[chosen]["pipeline_per_trust"] > incumbent_val["pipeline_per_trust"] \
                    and cand_true[chosen]["pipeline_per_trust"] <= incumbent_val["pipeline_per_trust"]:
                fake_adoptions += 1
            cfg = dict(cands[chosen])
    result = finalize_metrics(metrics, accounts)
    result.update({
        "arm": arm,
        "claimed_pipeline_per_trust": result["pipeline_per_trust"],
        "separation_gap": 0.0,
        "claimed_unsubscribe_rate": result["unsubscribe_rate_per_100_touches"],
        "claimed_complaint_rate": result["complaint_rate_per_100_touches"],
        "vetoes": len(veto_log),
        "veto_log": veto_log,
        "fake_adoptions": fake_adoptions,
        "adoptions": adoptions,
        "progressive_adoptions": progressive_adoptions,
        "epochs_evaluated": epochs_evaluated,
        "adoption_weeks": adoption_weeks,
        "adoption_workflows": adoption_workflows,
        "snapshots": snapshots,
        "validation_seed_log": validation_seed_log,
        "final_config": cfg,
        "empty_comparison": bool(adoptions == 0 and cfg == dict(BASE_CFG)),
    })
    return result
