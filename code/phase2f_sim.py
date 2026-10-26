"""
Phase 2f — 消融实验仿真器（新文件，不改动 gtm_sim.py / phase2d_* / paper-draft-v3.md）

合成数据声明：全部机制均为合成假设，不是真实厂商数据，不宣称真实
转化率、收入、厂商表现或跨厂商泛化。

与 2d 同口径（逐项对齐，不事后调参）：
- 同一仿真器：直接复用 phase2d_sim.policy_d / run_policy / _gate_pass /
  _proxy_pipeline_per_trust / _tampered，以及 gtm_sim.make_accounts /
  evolve_account / observed_intent / apply_action / finalize_metrics。
- 同一信号分布：主运行账户 make_accounts(n, seed)，验证集
  make_accounts(200, seed+1000) / 8 周 / 种子 seed+2000，与 2d 完全相同。
- 同一预算：gtm_sim.TRUST_BUDGET（30.0）+ 声誉 < 0.45 即 WAIT，见
  phase2d_sim._over_budget；门容忍与 2d 相同（退订 +0.2、投诉 +0.1、
  信任上限 1.10 倍、wait_share < 0.95、真值 > 现任）。
- 同一主指标：单位信任管道 pipeline_per_trust（冻结评估器 finalize_metrics）。
- 同一假采纳定义：采纳候选的内部分数高于现任内部分数，但验证集真值
  管道/信任不高于现任真值。有门臂内部分数 = 真值，故按定义假采纳应为 0。
- 同一伤害指标：退订率/100触达、投诉率/100触达、声誉变化（另报
  wait_share、信任消耗、总管道作上下文，不作主结论）。

新增臂（其余臂 B/C/D 直接复用 phase2d_sim.run_arm 重跑，不挪用 2d 数字）：
- STATIC（静态 G）：阈值层信任约束策略，无递归。配置全程固定为
  {workflow: W0, state: S0, threshold: 0.40, lambda: 3.0}。
  与 Phase 2c 的 G 对齐：2c 的 G 就是同一阈值/λ的静态信任约束策略
  （gtm_sim 阈值 0.40、λ 3.0、信任预算硬约束），2f 的 STATIC 是它在
  2d 仿真器（policy_d 的 W0/S0 分支）下的同一口径实现：W0 即基线 G 的
  动作选择，S0 即快照观测意图。STATIC 与 2d 各臂的关系：它是 2d 所有臂
  的 epoch 0 起点配置（B/C/D/E 均从该配置出发）；B 与 STATIC 在 B 的
  空比较种子上应完全相同（门一次未变），这是可检验的一致性锚点。
  STATIC 的 empty_comparison 恒为 True，但含义不同：不是“门未变”，而是
  “按设计从不尝试递归”，报告中必须区分，不得把 STATIC 的空比较与
  B 的空比较混为一类证据。
- W（工作流-only 有门）：仅工作流 W 递归、有门、评估器冻结，状态
  全程保持基线快照 S0。候选全部翻转工作流（W0<->W1），状态恒为 S0，
  阈值/λ变动仅作 2d 式微调（见 _candidates_w_only）；绝不含状态翻转
  候选，绝不含工作流不变的纯阈值候选（否则消融不纯）。
- S（状态-only 有门）：仅状态 S 递归、有门、评估器冻结，工作流
  全程保持基线 W0。候选全部翻转状态（S0<->S1），工作流恒为 W0
  （见 _candidates_s_only）；绝不含工作流翻转候选，绝不含状态不变的
  纯阈值候选。

候选集与 2d 的关系（必须明说）：2d 每 epoch 给 4 个候选，分别为
工作流-only、状态-only、工作流+状态、 工作流+阈值/λ变动；2f 的 W/S 臂
每 epoch 同样给 4 个候选，但全部约束在单层内（翻转该层 × 阈值/λ微调
组合），以保证“该层单独效应”可归因。候选数量相同、验证集相同、门
相同；候选构成不同是消融设计本身，不是口径漂移。
"""
from __future__ import annotations

import random
from typing import Dict, List

import gtm_sim
from gtm_sim import (
    make_accounts, evolve_account, apply_action, finalize_metrics, new_metrics,
)
import phase2d_sim
from phase2d_sim import (
    policy_d, run_policy, _gate_pass, _legal, WEEKS, EPOCH,
)

BASE_CFG: Dict = {"workflow": "W0", "state": "S0", "threshold": 0.40, "lambda": 3.0}


def _candidates_w_only(cfg: Dict) -> List[Dict]:
    """全部翻转工作流，状态恒为 S0。"""
    wf = cfg.get("workflow", "W0")
    other_wf = "W1" if wf == "W0" else "W0"
    thr = cfg.get("threshold", 0.40)
    lam = cfg.get("lambda", 3.0)
    return [
        {"workflow": other_wf, "state": "S0", "threshold": thr, "lambda": lam},
        {"workflow": other_wf, "state": "S0", "threshold": min(0.8, thr + 0.05), "lambda": lam},
        {"workflow": other_wf, "state": "S0", "threshold": max(0.15, thr - 0.05), "lambda": max(1.0, lam - 1.0)},
        {"workflow": other_wf, "state": "S0", "threshold": thr, "lambda": max(1.0, lam - 1.0)},
    ]


def _candidates_s_only(cfg: Dict) -> List[Dict]:
    """全部翻转状态，工作流恒为 W0。"""
    st = cfg.get("state", "S0")
    other_st = "S1" if st == "S0" else "S0"
    thr = cfg.get("threshold", 0.40)
    lam = cfg.get("lambda", 3.0)
    return [
        {"workflow": "W0", "state": other_st, "threshold": thr, "lambda": lam},
        {"workflow": "W0", "state": other_st, "threshold": min(0.8, thr + 0.05), "lambda": lam},
        {"workflow": "W0", "state": other_st, "threshold": max(0.15, thr - 0.05), "lambda": max(1.0, lam - 1.0)},
        {"workflow": "W0", "state": other_st, "threshold": thr, "lambda": max(1.0, lam - 1.0)},
    ]


def run_arm_f(arm: str, seed: int, n_accounts: int, weeks: int = WEEKS) -> Dict:
    """跑一 2f 新增臂。arm in {STATIC, W, S}。主运行循环逐行对齐 phase2d_sim.run_arm。"""
    assert arm in ("STATIC", "W", "S")
    cfg: Dict = dict(BASE_CFG)
    rng = random.Random(seed)
    accounts = make_accounts(n_accounts, seed)
    metrics = new_metrics()
    veto_log: List[Dict] = []
    fake_adoptions = 0
    adoptions = 0
    epochs_evaluated = 0
    for start in range(0, weeks, EPOCH):
        epoch_weeks = min(EPOCH, weeks - start)
        for _ in range(epoch_weeks):
            for acct in accounts:
                evolve_account(acct, rng)
                obs = acct.observed_intent(rng)
                action = _legal(acct, policy_d(acct, obs, cfg, rng))
                apply_action(acct, action, rng, metrics)
        if start + epoch_weeks >= weeks:
            break
        if arm == "STATIC":
            continue  # 静态 G：从不评估候选，从不递归
        # ---- 递归候选评估（与 2d 完全相同的验证集口径）----
        incumbent_val = run_policy(make_accounts(200, seed + 1000), cfg, 8, seed + 2000)
        cands = _candidates_w_only(cfg) if arm == "W" else _candidates_s_only(cfg)
        cand_true: List[Dict] = []
        for cand in cands:
            cand_true.append(run_policy(make_accounts(200, seed + 1000), cand, 8, seed + 2000))
        epochs_evaluated += 1
        best_idx = max(range(len(cands)), key=lambda i: cand_true[i]["pipeline_per_trust"])
        if _gate_pass(cand_true[best_idx], incumbent_val, 0.2, 0.1, 1.10):
            chosen = best_idx
        else:
            veto_log.append({"epoch": epochs_evaluated, "reason": "gate_failed",
                             "best_true": cand_true[best_idx]["pipeline_per_trust"],
                             "incumbent_true": incumbent_val["pipeline_per_trust"]})
            chosen = None
        if chosen is not None:
            adoptions += 1
            # 假采纳（有门臂内部分数 = 真值，门要求真值 > 现任，故应为 0；仍按定义计算）
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
        "epochs_evaluated": epochs_evaluated,
        "gate_changed": 0,
        "evaluator_version": 0,
        "final_config": cfg,
        # STATIC：按设计从不递归，恒为空比较（含义见模块说明，不得与 B 的门未变混同）。
        # W/S：与 2d 相同定义——所有 epoch 均未采纳、参数与初始相同。
        "empty_comparison": bool(adoptions == 0 and cfg == dict(BASE_CFG)),
    })
    return result
