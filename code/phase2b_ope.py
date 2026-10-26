"""Phase 2b 缺口 2：OPE 方法论单元测试（核心交付，务必诚实）。

设计说明（先读，再引用）：
- 本文件只做“评估方法本身算得对不对”的单元测试，不是商业验证。
  仿真机制是假设，不是测量；OPE 在合成设定下成立，不等于在真实日志下成立。
- 实验 OPE-1（孤立 bandit）：用仿真器生成一周决策的上下文与结果，
  logging policy 已知，目标策略为六基线的确定性版（WAIT-heavy 除外，
  它本身是随机的，pi 用解析值）。这样可以干净地检验 IPS / SNIPS / DM / DR
  在样本量、探索率、隐藏混杂三种条件下的排序恢复能力。
- 实验 OPE-2（序贯 naive）：用 24 周完整轨迹做日志，再用“把每周当独立
  bandit 样本”的 naive DR 去估计六基线排序，与 fresh run 的真值排序对比。
  本实验的预期就是暴露 naive 方法在序贯场景下的失效 —— 如果它恰好恢复了，
  也必须说明那是在本合成机制、且上下文已含声誉/触达历史等状态特征的前提下，
  不能外推为“真实 GTM 日志可以直接用 bandit OPE”。
- G+ 有门/无门在 OPE-2 中的处理：其 epoch 参数演化与 v0 simulate_gplus
  完全一致（验证集种子、候选扰动、门规则均复用 gtm_sim_phase2b 的函数），
  因此第 w 周的目标动作是 (epoch 参数, 上下文) 的确定性函数，pi 可计算。
  在 OPE-1（一周）中，有门/无门尚未递归，退化为 G，故 OPE-1 用 G 的三个
  阈值变体代替有门/无门，并明确标注这一点，不假装测了递归。

奖励定义：单步奖励 = 该周管道增量（合成单位）；信任消耗单独记录，
OPE 估计的是期望管道，不是 Pipeline-per-Trust 比率。比率需用
“管道期望 / 信任期望”之比另行估计，本文件同时报告两者，避免把比率
当成可直接做 IPS 的奖励。

全部结果均为合成数据。
"""
from __future__ import annotations

import copy
import math
import random
import statistics
from dataclasses import replace
from typing import Dict, List, Tuple

import gtm_sim_phase2b as sim

# ---------------------------------------------------------------- 通用

def obs_bucket(obs: float) -> str:
    if obs < 0.25:
        return "low"
    if obs < 0.40:
        return "mid"
    if obs < 0.65:
        return "high"
    return "veryhigh"


def rep_bucket(rep: float) -> str:
    return "low" if rep < 0.7 else "high"


def allowed_actions(track: str) -> List[str]:
    if track == "t1":
        return sim.TRACK1_ACTIONS + ["STOP_COOLING"]
    return list(sim.TRACK2_ACTIONS)


def logging_action_and_prop(acct, obs: float, rng: random.Random,
                            eps: float = 0.3, warm: bool = False, warm_override: float = 0.5) -> Tuple[str, float]:
    """logging policy：以 1-eps 跟随 G（阈值 .40, lambda 3），以 eps 均匀探索。
    warm 混杂变体：warm 账户有 50% 概率被直接改写为 DEEP / PARTNER_TOUCH，
    且 propensity 按混合分布计算（不是事后编造）。"""
    base = sim.policy_g(acct, obs, {"threshold": 0.40, "lambda": 3.0}, rng)
    acts = allowed_actions(acct.track)
    # eps-greedy 分布
    dist = {a: eps / len(acts) for a in acts}
    dist[base] = dist.get(base, 0.0) + (1 - eps)
    if warm:
        hot = "DEEP" if acct.track == "t1" else "PARTNER_TOUCH"
        dist = {a: (1 - warm_override) * p + (warm_override if a == hot else 0.0) for a, p in dist.items()}
    # 按分布采样
    r = rng.random()
    cum = 0.0
    for a, p in dist.items():
        cum += p
        if r <= cum:
            return a, p
    return acts[-1], dist[acts[-1]]


def target_action(acct, obs: float, name: str, rng: random.Random,
                  gated_params_history=None, week: int = 0) -> Tuple[str, float]:
    """确定性目标策略的动作与 pi（WAIT-heavy 除外，pi 用解析值）。"""
    if name == "wait_heavy":
        # pi 解析：WAIT 0.9，LIGHT/PARTNER_TOUCH 0.1，其余 0
        if rng.random() < 0.9:
            return "WAIT", 0.9
        a = "LIGHT" if acct.track == "t1" else "PARTNER_TOUCH"
        return a, 0.1
    if name == "reply_greedy":
        a = sim.policy_reply_greedy(acct, obs, {}, rng)
    elif name == "human_rules":
        a = sim.policy_human_rules(acct, obs, {}, rng)
    elif name == "G":
        a = sim.policy_g(acct, obs, {"threshold": 0.40, "lambda": 3.0}, rng)
    elif name == "G_0.35":
        a = sim.policy_g(acct, obs, {"threshold": 0.35, "lambda": 3.0}, rng)
    elif name == "G_0.45":
        a = sim.policy_g(acct, obs, {"threshold": 0.45, "lambda": 3.0}, rng)
    elif name in ("G+_gated", "G+_ungated"):
        params = (gated_params_history or {}).get(week // 8, {"threshold": 0.40, "lambda": 3.0})
        a = sim.policy_g(acct, obs, params, rng)
    else:
        raise ValueError(name)
    # 合法性（与 simulate 一致）
    if acct.track == "t1" and a not in sim.TRACK1_ACTIONS + ["STOP_COOLING"]:
        a = "WAIT"
    if acct.track == "t2" and a not in sim.TRACK2_ACTIONS:
        a = "WAIT"
    return a, 1.0


def context_key(ctx: Dict, use_warm: bool = False) -> Tuple:
    key = (ctx["track"], ctx["segment"], ctx["obs_bucket"], ctx["rep_bucket"],
           ctx["touches_bucket"], ctx["qualified"])
    if use_warm:
        key = key + (ctx.get("warm", False),)
    return key


def fit_q(log: List[Dict], use_warm: bool = False) -> Tuple[Dict, Dict, float]:
    """分组均值 Q(x,a)；空组回退到动作均值，再回退到全局均值。"""
    from collections import defaultdict
    sums, counts = defaultdict(float), defaultdict(int)
    a_sums, a_counts = defaultdict(float), defaultdict(int)
    total, n = 0.0, 0
    for row in log:
        k = (context_key(row, use_warm), row["action"])
        sums[k] += row["reward"]; counts[k] += 1
        a_sums[row["action"]] += row["reward"]; a_counts[row["action"]] += 1
        total += row["reward"]; n += 1
    q = {k: sums[k] / counts[k] for k in sums}
    a_mean = {a: a_sums[a] / a_counts[a] for a in a_sums}
    g_mean = total / max(1, n)
    return q, a_mean, g_mean


def q_value(q, a_mean, g_mean, ctx, action, use_warm=False) -> float:
    k = (context_key(ctx, use_warm), action)
    if k in q:
        return q[k]
    if action in a_mean:
        return a_mean[action]
    return g_mean


def estimate(log: List[Dict], target: str, gated_params_history=None,
             use_warm: bool = False, cross_fit: bool = True) -> Dict:
    """IPS / SNIPS / DM / DR（bandit 形式）。对确定性目标，pi 为 0/1；
    WAIT-heavy 用解析 pi。注意：本估计把每周样本当独立样本，序贯场景下
    这是有偏的近似（见 OPE-2），此处先算出数，再与真值对比揭露偏差。
    cross_fit=True 时用 2 折交叉拟合 Q（按 account_id 分折，若无则按行号），
    避免 Q 在同一批数据上拟合又评估的 in-sample 过拟合。"""
    if cross_fit:
        # 分折：有 account_id 按账户奇偶分，无则按行号奇偶分
        def fold_key(row, idx):
            return row.get("account_id", idx) % 2
        folds = [[r for i, r in enumerate(log) if fold_key(r, i) == f] for f in (0, 1)]
        totals = {"ips_num": 0.0, "ips_den": 0.0, "dm_sum": 0.0, "dr_sum": 0.0, "n": 0}
        for eval_fold, fit_fold in [(folds[0], folds[1]), (folds[1], folds[0])]:
            if not eval_fold or not fit_fold:
                continue
            sub = _estimate_with_q(eval_fold, target, gated_params_history, use_warm, fit_fold)
            totals["ips_num"] += sub["ips_num"]; totals["ips_den"] += sub["ips_den"]
            totals["dm_sum"] += sub["dm_sum"]; totals["dr_sum"] += sub["dr_sum"]; totals["n"] += len(eval_fold)
        n = totals["n"] or 1
        return {"IPS": totals["ips_num"] / n,
                "SNIPS": totals["ips_num"] / totals["ips_den"] if totals["ips_den"] else 0.0,
                "DM": totals["dm_sum"] / n, "DR": totals["dr_sum"] / n,
                "DR_trust_per_step": None, "n": totals["n"]}
    q, a_mean, g_mean = fit_q(log, use_warm)
    sub = _estimate_with_q(log, target, gated_params_history, use_warm, None, (q, a_mean, g_mean))
    n = len(log) or 1
    return {"IPS": sub["ips_num"] / n,
            "SNIPS": sub["ips_num"] / sub["ips_den"] if sub["ips_den"] else 0.0,
            "DM": sub["dm_sum"] / n, "DR": sub["dr_sum"] / n,
            "DR_trust_per_step": None, "n": len(log)}


def _estimate_with_q(eval_log, target, gated_params_history, use_warm, fit_log, prefit=None):
    if prefit is not None:
        q, a_mean, g_mean = prefit
    else:
        q, a_mean, g_mean = fit_q(fit_log, use_warm)
    ips_num, ips_den, dm_sum, dr_sum, trust_num = 0.0, 0.0, 0.0, 0.0, 0.0
    for row in eval_log:
        # 目标动作：需要重建当时的 rule 状态（human_rules）与 epoch 参数
        # 简化：对 OPE-2，log 中已存 target_action 字典（见生成函数），此处
        # 若 log 行含 target_actions 则直接取，否则用当前上下文重算（OPE-1）。
        if "target_actions" in row and target in row["target_actions"]:
            t_action, t_pi = row["target_actions"][target]
        else:
            # OPE-1：上下文即当前账户状态的快照，重算需一个临时账户对象
            # 由调用方在 log 行里放入 acct_snapshot 的关键字段；这里用 row 的
            # obs/track 等重建一个最小账户（仅用于策略函数，不用于奖励）。
            acct = sim.Account(id=0, track=row["track"], segment=row["segment"],
                               intent=row["obs"], reputation=1.0 if row["rep_bucket"] == "high" else 0.6)
            acct._rule_touches = row.get("rule_touches", 0)  # type: ignore
            acct.partner_effectiveness = row.get("partner_effectiveness", 0.5)
            rng = random.Random(0)
            t_action, t_pi = target_action(acct, row["obs"], target, rng,
                                           gated_params_history, row.get("week", 0))
        # DM 项：sum_a pi(a|x) Q(x,a) —— 确定性目标退化为 Q(x, t_action)；
        # WAIT-heavy 需对两个可能动作加权，近似用其解析分布的期望。
        if target == "wait_heavy":
            dm = 0.9 * q_value(q, a_mean, g_mean, row, "WAIT", use_warm)
            hot = "LIGHT" if row["track"] == "t1" else "PARTNER_TOUCH"
            dm += 0.1 * q_value(q, a_mean, g_mean, row, hot, use_warm)
        else:
            dm = q_value(q, a_mean, g_mean, row, t_action, use_warm)
        dm_sum += dm
        # IPS / DR：只有 logged action 与目标分布重叠时才有修正项
        # 确定性目标：t_pi=1 时，仅当 logged == t_action 才有权重 1/mu
        if target == "wait_heavy":
            # logged action 的目标概率
            if row["action"] == "WAIT":
                pi_logged = 0.9
            elif row["action"] == ("LIGHT" if row["track"] == "t1" else "PARTNER_TOUCH"):
                pi_logged = 0.1
            else:
                pi_logged = 0.0
        else:
            pi_logged = 1.0 if row["action"] == t_action else 0.0
        w = pi_logged / row["propensity"] if row["propensity"] > 0 else 0.0
        ips_num += w * row["reward"]
        ips_den += w
        trust_num += w * row.get("trust_cost", 0.0)
        q_logged = q_value(q, a_mean, g_mean, row, row["action"], use_warm)
        dr_sum += dm + w * (row["reward"] - q_logged)
    return {"ips_num": ips_num, "ips_den": ips_den, "dm_sum": dm_sum, "dr_sum": dr_sum}


# ---------------------------------------------------------------- OPE-1 孤立 bandit

def generate_one_step_log(n: int, seed: int, eps: float = 0.3,
                          confounded: bool = False, warm_prob: float = 0.3,
                          warm_boost: float = 1.8, warm_override: float = 0.5) -> List[Dict]:
    rng = random.Random(seed)
    log = []
    accounts = sim.make_accounts(n, seed)
    warm_rng = random.Random(seed + 777)
    for acct in accounts:
        for _ in range(12):
            sim.evolve_account(acct, warm_rng)
    for acct in accounts:
        warm = (rng.random() < warm_prob) if confounded else False
        obs = acct.observed_intent(rng)
        action, prop = logging_action_and_prop(acct, obs, rng, eps=eps, warm=warm, warm_override=warm_override)
        # 在账户副本上执行一步，测管道增量
        acct2 = copy.deepcopy(acct)
        acct2.touches_last4 = [0]  # apply_action 要求至少一周的触达记录位（见 evolve）
        m = sim.new_metrics()
        before = m["pipeline"]
        sim.apply_action(acct2, action, rng, m)
        reward = m["pipeline"] - before
        if confounded and warm and reward > 0:
            reward *= warm_boost  # 隐藏混杂：warm 账户的奖励被放大，但 OPE 上下文不含 warm
        # 观测-only propensity：忽略 warm 改写，只按 eps-greedy G 计算。
        # 若估计器用它代替真实 propensity，就会引入混杂偏误（见 OPE-1d 变体）。
        base_g = sim.policy_g(acct, obs, {"threshold": 0.40, "lambda": 3.0}, rng)
        n_acts = len(allowed_actions(acct.track))
        prop_obs = ((1 - eps) + eps / n_acts) if action == base_g else (eps / n_acts)
        log.append({
            "propensity_observed_only": prop_obs,
            "track": acct.track, "segment": acct.segment, "obs": obs,
            "obs_bucket": obs_bucket(obs), "rep_bucket": rep_bucket(acct.reputation),
            "touches_bucket": 0, "qualified": False, "warm": warm,
            "rule_touches": 0, "partner_effectiveness": acct.partner_effectiveness,
            "action": action, "propensity": prop, "reward": reward,
            "trust_cost": sim.ACTIONS[action]["trust_cost"] if action in sim.ACTIONS else 0.0,
            "week": 0,
        })
    return log


def ground_truth_one_step(n: int, seed: int, targets: List[str],
                          confounded: bool = False, warm_prob: float = 0.3,
                          warm_boost: float = 1.8) -> Dict[str, float]:
    rng = random.Random(seed + 999)
    accounts = sim.make_accounts(n, seed)
    warm_rng = random.Random(seed + 888)
    for acct in accounts:
        for _ in range(12):
            sim.evolve_account(acct, warm_rng)
    totals = {t: 0.0 for t in targets}
    # warm 分布与 log 生成一致（同一账户顺序、同一 rng 序列会不同，故用独立
    # 账户集 + 独立 warm 抽取，均值意义上的真值，不是逐账户配对真值）
    warm_rng = random.Random(seed + 555)
    for acct in accounts:
        warm = (warm_rng.random() < warm_prob) if confounded else False
        for t in targets:
            acct2 = copy.deepcopy(acct)
            acct2.touches_last4 = [0]
            obs = acct2.observed_intent(rng)
            a, _ = target_action(acct2, obs, t, rng)
            m = sim.new_metrics()
            before = m["pipeline"]
            sim.apply_action(acct2, a, rng, m)
            r = m["pipeline"] - before
            if confounded and warm and r > 0:
                r *= warm_boost
            totals[t] += r
    return {t: totals[t] / n for t in targets}


def rank_order(d: Dict[str, float]) -> List[str]:
    return sorted(d.keys(), key=lambda k: -d[k])


def spearman(a: List[str], b: List[str]) -> float:
    # a, b 为同一集合的排序；返回 Spearman（小样本，手工算）
    ra = {x: i for i, x in enumerate(a)}
    rb = {x: i for i, x in enumerate(b)}
    xs = [ra[x] for x in a]
    ys = [rb[x] for x in a]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else 0.0


# ---------------------------------------------------------------- OPE-2 序贯 naive

def gated_params_history(seed: int, gated: bool) -> Dict[int, Dict]:
    """复现 simulate_gplus 的 epoch 参数演化（验证集种子与 v0 一致），
    返回 {epoch_index: params}。epoch=8 周。"""
    params = {"threshold": 0.40, "lambda": 3.0}
    hist = {0: dict(params)}
    # 24 周 = 3 个 epoch，中间有 2 次递归评估（第 8、16 周后）
    for epoch_idx in range(2):
        incumbent_val = sim.simulate(sim.make_accounts(80, seed + 1000), sim.policy_g_static,
                                     params, 8, seed + 2000)
        best, best_val, best_reply, best_reply_val = None, None, None, None
        for delta in sim.CANDIDATE_DELTAS:
            cand = sim._apply_delta(params, delta)
            val = sim.simulate(sim.make_accounts(80, seed + 1000), sim.policy_g_static,
                               cand, 8, seed + 2000)
            if best_val is None or val["pipeline_per_trust"] > best_val["pipeline_per_trust"]:
                best, best_val = cand, val
            if best_reply_val is None or val["replies"] > best_reply_val["replies"]:
                best_reply, best_reply_val = cand, val
        if gated:
            if best_val is not None and sim._gate_pass(best_val, incumbent_val):
                params = best
            # 否则回滚（参数不变）
        else:
            if best_reply is not None:
                params = best_reply
        hist[epoch_idx + 1] = dict(params)
    return hist


def generate_sequential_log(n_accounts: int, weeks: int, seed: int, eps: float = 0.3):
    rng = random.Random(seed)
    accounts = sim.make_accounts(n_accounts, seed)
    # G+ 有门/无门的 epoch 参数历史必须分开算（两者演化不同），且只算一次
    hist_gated = gated_params_history(seed, gated=True)
    hist_ungated = gated_params_history(seed, gated=False)
    log = []
    for acct in accounts:
        # 每个账户独立轨迹；logging policy 每周按 eps-greedy G 执行
        for week in range(weeks):
            sim.evolve_account(acct, rng)
            obs = acct.observed_intent(rng)
            action, prop = logging_action_and_prop(acct, obs, rng, eps=eps, warm=False)
            # 记录本周所有目标策略的动作（用于 OPE 估计，避免事后重建 rule 状态）
            t_actions = {}
            for t in ["reply_greedy", "human_rules", "wait_heavy", "G", "G+_gated", "G+_ungated"]:
                # human_rules 需要当前 rule 状态：用副本账户计算目标动作，原账户不受影响
                acct_copy = copy.deepcopy(acct)
                hist = hist_gated if t == "G+_gated" else (hist_ungated if t == "G+_ungated" else None)
                a, pi = target_action(acct_copy, obs, t, rng, hist, week)
                t_actions[t] = (a, pi)
            # Pre-action context（关键修正）：声誉、触达历史、是否已合格必须取动作前的值，
            # 否则 DM/DR 会把结果泄漏进上下文，导致系统性高估（见报告）。
            rep_before = acct.reputation
            touches_before = sum(acct.touches_last4[-4:]) if acct.touches_last4 else 0
            qualified_before = acct.qualified
            partner_before = acct.partner_effectiveness
            m = sim.new_metrics()
            before_pipe, before_trust = m["pipeline"], m["trust_consumed"]
            sim.apply_action(acct, action, rng, m)
            log.append({
                "account_id": acct.id,
                "track": acct.track, "segment": acct.segment, "obs": obs,
                "obs_bucket": obs_bucket(obs), "rep_bucket": rep_bucket(rep_before),
                "touches_bucket": touches_before,
                "qualified": qualified_before,
                "warm": False, "rule_touches": getattr(acct, "_rule_touches", 0),
                "partner_effectiveness": partner_before,
                "action": action, "propensity": prop,
                "reward": m["pipeline"] - before_pipe,
                "trust_cost": m["trust_consumed"] - before_trust,
                "week": week, "target_actions": t_actions,
            })
    return log


# 缓存：避免每行重复算 gated 参数历史（同一 seed 只算一次）
gated_params_history_cache: Dict[int, Dict] = {}
