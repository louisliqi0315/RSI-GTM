"""Phase 2c 任务一：完整序贯 OPE（替代已被证伪的 naive bandit 方法）。

全部结果均为合成数据。仅 Python 标准库。

核心设计（先读，再引用）：
1. 轨迹级回报，吸收态安全：管道奖励只在账户首次合格那一周计一次，
   合格后所有后续周的管道奖励恒为 0。评估目标是整条轨迹的总管道
   E[R] 与总信任消耗 E[T]，主指标是 E[R]/E[T]（期望之比），不是
   每周奖励的平均，也不是 E[R/T]。朴素按周 DR 把“尚未合格周的上下文”
   当成独立样本，会重复计算本应只发生一次的管道——这正是 Phase 2b
   测得 1.7-2.1 倍高估的机制，本文件从设计上杜绝它。
2. 动作前状态，杜绝泄漏：所有上下文（声誉、触达历史、是否已合格、
   伙伴效能）一律取动作前值；下一状态取下一周的动作前上下文。
3. 两种序贯方法对照：
   - 方法 A：Fitted Q Evaluation（FQE，分组均值 Q，2 折按账户交叉拟合，
     向后递推 30 轮或收敛）。Q_pipe 在已合格状态下恒为 0；Q_trust 在
     已合格后仍继续累计（策略在合格后仍可能触达并消耗信任，这是
     仿真器的真实行为，不得把信任也截断）。
   - 方法 B：序贯双重稳健（per-decision DR），用方法 A 的 Q 作基线，
     重要性权重为累积乘积 rho_{1:t}。对确定性目标策略，rho 在首次
     与目标动作不一致时归零并截断——这是方法本身的性质，不是 bug，
     本文件用有效样本量（ESS）与自助标准误把它量化出来。
4. 人工规则（human_rules）不在序贯 OPE 排名内：它的内部计数器是
   目标策略自身的反事实历史，无法从 logging 轨迹恢复（Phase 2b 已证），
   本文件只在真值（fresh run）中报告它，OPE 排名明确排除并注明。
   这不是遗漏，是可识别性边界。
5. 有门/无门的目标动作：epoch 参数历史与 Phase 2b 完全一致
   （phase2b_ope.gated_params_history），按周 // 8 取 epoch 参数，
   与 logging 种子绑定，不跨种子比较。
6. Rosenbaum 敏感性（数值化，见 phase2c_seqope_run.py）：
   (a) Wilcoxon 符号秩的 Gamma 界（配对种子差分，DP 精确计算最坏
   情况下的单侧 p 值上界）；(b) 未观测混杂 warm 的网格：warm 账户
   的 logging 动作被改写、奖励被放大，估计器忽略 warm，找翻转阈值。
"""
from __future__ import annotations

import copy
import math
import random
import statistics
from collections import defaultdict
from typing import Dict, List, Tuple

import gtm_sim_phase2b as sim
from phase2b_ope import (gated_params_history, logging_action_and_prop,
                         obs_bucket, rep_bucket, target_action)

POLICIES = ["reply_greedy", "wait_heavy", "G", "G+_gated", "G+_ungated"]
# human_rules 仅真值，见模块说明第 4 条。
ALL_SIX = POLICIES + ["human_rules"]


def partner_bucket(v: float) -> str:
    if v < 0.6:
        return "low"
    if v < 0.8:
        return "mid"
    return "high"


def state_key(row: Dict) -> Tuple:
    return (row["track"], row["segment"], row["obs_bucket"], row["rep_bucket"],
            row["touches_bucket"], row["qualified"], partner_bucket(row["partner_effectiveness"]),
            row["week"] // 8)


def target_pi(row: Dict, policy: str) -> Dict[str, float]:
    """目标策略在该周的动作分布（确定性策略为 0/1；wait_heavy 为解析分布）。"""
    t_action, t_pi = row["target_actions"][policy]
    if policy == "wait_heavy":
        hot = "LIGHT" if row["track"] == "t1" else "PARTNER_TOUCH"
        return {"WAIT": 0.9, hot: 0.1}
    return {t_action: 1.0}


# ---------------------------------------------------------------- 暖混杂日志生成

def generate_sequential_log_warm(n_accounts: int, weeks: int, seed: int, eps: float = 0.3,
                                 warm_prob: float = 0.0, warm_boost: float = 1.0,
                                 warm_override: float = 0.0):
    """镜像 phase2b_ope.generate_sequential_log，唯一新增是 warm 混杂：
    warm 账户（按 seed+9000 的独立 RNG 顺序抽取，与真值函数的抽取一致）
    的 logging 动作以 warm_override 概率被改写为 DEEP / PARTNER_TOUCH，
    且其管道增量在日志中被放大 warm_boost 倍。估计器看不到 warm 字段
    之外的任何信息（FQE 状态键不含 warm），因此 warm 是未观测混杂。
    warm_prob=0 时退化为 phase2b 的无混杂日志（动作分布与原函数一致，
    仅 RNG 顺序不同，故数值不必与 phase2b 逐行相同，分布一致即可）。"""
    rng = random.Random(seed)
    warm_rng = random.Random(seed + 9000)
    accounts = sim.make_accounts(n_accounts, seed)
    warm_flags = [warm_rng.random() < warm_prob for _ in accounts]
    hist_gated = gated_params_history(seed, gated=True)
    hist_ungated = gated_params_history(seed, gated=False)
    log = []
    for acct, warm in zip(accounts, warm_flags):
        for week in range(weeks):
            sim.evolve_account(acct, rng)
            obs = acct.observed_intent(rng)
            action, prop = logging_action_and_prop(acct, obs, rng, eps=eps, warm=False)
            if warm and rng.random() < warm_override:
                hot = "DEEP" if acct.track == "t1" else "PARTNER_TOUCH"
                # 混合 propensity：原分布以 (1-override) 保留，override 质量移到 hot
                acts = sim.TRACK1_ACTIONS + ["STOP_COOLING"] if acct.track == "t1" else list(sim.TRACK2_ACTIONS)
                base_dist = {}
                # 重建 eps-greedy G 分布（与 logging_action_and_prop 一致）
                base_g = sim.policy_g(acct, obs, {"threshold": 0.40, "lambda": 3.0}, rng)
                for a in acts:
                    base_dist[a] = eps / len(acts)
                base_dist[base_g] = base_dist.get(base_g, 0.0) + (1 - eps)
                prop = (1 - warm_override) * base_dist[action] + (warm_override if action == hot else 0.0)
                # 注意：prop 是“改写后实际执行该动作的概率”在旧动作下的值；
                # 若改写发生，实际动作应为 hot。处理：若本轮被改写，动作改为 hot，
                # 其 propensity 为混合分布在 hot 处的值。
                action = hot
                prop = (1 - warm_override) * base_dist[hot] + warm_override
            t_actions = {}
            for t in ALL_SIX:
                acct_copy = copy.deepcopy(acct)
                hist = hist_gated if t == "G+_gated" else (hist_ungated if t == "G+_ungated" else None)
                a, pi = target_action(acct_copy, obs, t, rng, hist, week)
                t_actions[t] = (a, pi)
            rep_before = acct.reputation
            touches_before = sum(acct.touches_last4[-4:]) if acct.touches_last4 else 0
            qualified_before = acct.qualified
            partner_before = acct.partner_effectiveness
            m = sim.new_metrics()
            before_pipe, before_trust = m["pipeline"], m["trust_consumed"]
            sim.apply_action(acct, action, rng, m)
            pipe_inc = m["pipeline"] - before_pipe
            if warm and pipe_inc > 0:
                pipe_inc *= warm_boost
            log.append({
                "account_id": acct.id, "track": acct.track, "segment": acct.segment,
                "obs": obs, "obs_bucket": obs_bucket(obs), "rep_bucket": rep_bucket(rep_before),
                "touches_bucket": touches_before, "qualified": qualified_before,
                "warm": warm, "partner_effectiveness": partner_before,
                "action": action, "propensity": prop,
                "reward": pipe_inc, "trust_cost": m["trust_consumed"] - before_trust,
                "week": week, "target_actions": t_actions,
            })
    return log


def fresh_run_warm(policy: str, n_accounts: int, weeks: int, seed: int,
                   warm_prob: float = 0.0, warm_boost: float = 1.0) -> Dict:
    """同一人口（同 seed 的初始账户、同顺序 warm 抽取）下的真值 fresh run。
    warm 只放大管道增量，不改变策略行为（目标策略看不到 warm，与估计器
    的信息集一致）；信任消耗不受 warm 影响。"""
    warm_rng = random.Random(seed + 9000)
    accounts = sim.make_accounts(n_accounts, seed)
    warm_flags = [warm_rng.random() < warm_prob for _ in accounts]
    hist_gated = gated_params_history(seed, gated=True)
    hist_ungated = gated_params_history(seed, gated=False)
    rng = random.Random(seed + 5000)
    metrics = sim.new_metrics()
    for acct, warm in zip(accounts, warm_flags):
        for week in range(weeks):
            sim.evolve_account(acct, rng)
            obs = acct.observed_intent(rng)
            if policy == "human_rules":
                a = sim.policy_human_rules(acct, obs, {}, rng)
            elif policy in ("G+_gated", "G+_ungated"):
                hist = hist_gated if policy == "G+_gated" else hist_ungated
                params = hist.get(week // 8, {"threshold": 0.40, "lambda": 3.0})
                a = sim.policy_g(acct, obs, params, rng)
            elif policy == "wait_heavy":
                a = "WAIT" if rng.random() < 0.9 else ("LIGHT" if acct.track == "t1" else "PARTNER_TOUCH")
            elif policy == "reply_greedy":
                a = sim.policy_reply_greedy(acct, obs, {}, rng)
            elif policy == "G":
                a = sim.policy_g(acct, obs, {"threshold": 0.40, "lambda": 3.0}, rng)
            else:
                raise ValueError(policy)
            if acct.track == "t1" and a not in sim.TRACK1_ACTIONS + ["STOP_COOLING"]:
                a = "WAIT"
            if acct.track == "t2" and a not in sim.TRACK2_ACTIONS:
                a = "WAIT"
            m = sim.new_metrics()
            before = m["pipeline"]
            sim.apply_action(acct, a, rng, m)
            inc = m["pipeline"] - before
            if warm and inc > 0:
                inc *= warm_boost
            metrics["decisions"] += m["decisions"]
            metrics["touches"] += m["touches"]
            metrics["replies"] += m["replies"]
            metrics["qualified_count"] += m["qualified_count"]
            metrics["pipeline"] += inc
            metrics["trust_consumed"] += m["trust_consumed"]
            metrics["unsubscribes"] += m["unsubscribes"]
            metrics["complaints"] += m["complaints"]
            metrics["wait_count"] += m["wait_count"]
            metrics["cooling_count"] += m["cooling_count"]
            metrics["retained_usage"] += m["retained_usage"]
    fin = sim.finalize_metrics(metrics, accounts)
    fin["per_account_pipeline"] = metrics["pipeline"] / n_accounts
    fin["per_account_trust"] = metrics["trust_consumed"] / n_accounts
    return fin


# ---------------------------------------------------------------- FQE

def _fit_q(transitions, reward_key: str, iters: int = 30):
    """分组均值 Q，迭代向后递推。transitions 为 (row, next_row_or_None, target_dist)
    形式的列表在调用方展开；此处为通用拟合器，next_value 由调用方传入的
    当前 Q 表计算（见 fit_q_fqe）。为避免循环依赖，本函数只做一轮拟合，
    迭代在 fit_q_fqe 中驱动。"""
    sums, counts = defaultdict(float), defaultdict(int)
    a_sums, a_counts = defaultdict(float), defaultdict(int)
    total, n = 0.0, 0
    for key, action, target in transitions:
        sums[(key, action)] += target
        counts[(key, action)] += 1
        a_sums[action] += target
        a_counts[action] += 1
        total += target
        n += 1
    q = {k: sums[k] / counts[k] for k in sums}
    a_mean = {a: a_sums[a] / a_counts[a] for a in a_sums}
    g_mean = total / max(1, n)
    return q, a_mean, g_mean


def _q_lookup(q, a_mean, g_mean, key, action, qualified: bool, reward_key: str) -> float:
    if reward_key == "reward" and qualified:
        return 0.0  # 吸收态：已合格后未来管道恒为 0（信任不适用此规则）
    k = (key, action)
    if k in q:
        return q[k]
    if action in a_mean:
        return a_mean[action]
    return g_mean


def fit_q_fqe(trajectories, policy: str, reward_key: str, iters: int = 30):
    """对一条策略做 FQE。trajectories: List[List[row]]（按周排序）。
    返回 (q, a_mean, g_mean)。Q 表键为 (state_key, action)。"""
    # 预计算每条轨迹每步的 next_key 与目标分布
    q, a_mean, g_mean = {}, {}, 0.0
    for _ in range(iters):
        transitions = []
        for traj in trajectories:
            for i, row in enumerate(traj):
                nxt = traj[i + 1] if i + 1 < len(traj) else None
                # V_next：下一状态在目标策略下的 Q 期望；终态或下一状态已合格
                # （管道）时为 0。注意：下一状态的 qualified 是下一周动作前值，
                # 它反映本周期合格与否，恰好是吸收态判断。
                if nxt is None:
                    v_next = 0.0
                else:
                    dist = target_pi(nxt, policy)
                    v_next = sum(p * _q_lookup(q, a_mean, g_mean, state_key(nxt), a,
                                               nxt["qualified"], reward_key)
                                 for a, p in dist.items())
                r = row[reward_key]
                # 管道：若本步前已合格，本步奖励在生成时恒为 0，目标即 V_next（=0）
                target = r + v_next
                transitions.append((state_key(row), row["action"], target))
        new_q, new_a, new_g = _fit_q(transitions, reward_key)
        change = 0.0
        for k, v in new_q.items():
            change = max(change, abs(v - q.get(k, 0.0)))
        q, a_mean, g_mean = new_q, new_a, new_g
        if change < 1e-6:
            break
    return q, a_mean, g_mean


def fqe_value(trajectories, policy: str, reward_key: str, q_pack) -> float:
    """初始状态分布下的 V：对每条轨迹的第 0 周状态取目标分布下的 Q 期望并平均。
    第 0 周状态是策略无关的（动作前、演化后），故可直接用 logging 轨迹的
    初始状态分布，无需重要性加权。"""
    q, a_mean, g_mean = q_pack
    vals = []
    for traj in trajectories:
        if not traj:
            continue
        row = traj[0]
        dist = target_pi(row, policy)
        vals.append(sum(p * _q_lookup(q, a_mean, g_mean, state_key(row), a,
                                      row["qualified"], reward_key) for a, p in dist.items()))
    return statistics.mean(vals) if vals else 0.0


def cross_fitted_fqe(trajectories, policy: str):
    """2 折按账户交叉拟合：A 折拟合 Q、评估 B 折初始值，反之亦然；
    返回管道期望、信任期望、比率（聚合期望之比）。"""
    by_fold = {0: [], 1: []}
    for traj in trajectories:
        if traj:
            by_fold[traj[0]["account_id"] % 2].append(traj)
    pipe_vals, trust_vals, counts = [], [], []
    for fit_fold, eval_fold in [(0, 1), (1, 0)]:
        fit_trajs = by_fold[fit_fold]
        eval_trajs = by_fold[eval_fold]
        if not fit_trajs or not eval_trajs:
            continue
        q_pipe = fit_q_fqe(fit_trajs, policy, "reward")
        q_trust = fit_q_fqe(fit_trajs, policy, "trust_cost")
        vp = fqe_value(eval_trajs, policy, "reward", q_pipe)
        vt = fqe_value(eval_trajs, policy, "trust_cost", q_trust)
        pipe_vals.append(vp * len(eval_trajs))
        trust_vals.append(vt * len(eval_trajs))
        counts.append(len(eval_trajs))
    n = sum(counts) or 1
    vp = sum(pipe_vals) / n
    vt = sum(trust_vals) / n
    return {"V_pipeline": vp, "V_trust": vt, "ratio": vp / vt if vt > 0 else 0.0}


def trajectories_from_log(log):
    by_acct = defaultdict(list)
    for row in log:
        by_acct[row["account_id"]].append(row)
    trajs = []
    for aid in sorted(by_acct):
        trajs.append(sorted(by_acct[aid], key=lambda r: r["week"]))
    return trajs


def sequential_dr(trajectories, policy: str, q_pipe_pack, q_trust_pack):
    """序贯 DR（管道）：V0 + sum_t rho_{1:t} (r_t + V_{t+1} - Q_t)。
    rho 为累积乘积；确定性目标在首次不匹配时归零并截断后续项。
    信任的 DR 同理（吸收态不截断信任，但管道项在合格后恒为 0）。
    返回均值、自助标准误（500 次按轨迹重抽样，固定种子）、ESS 序列。"""
    q_pipe, a_pipe, g_pipe = q_pipe_pack
    # 先算每条轨迹的 DR 贡献（管道）与 rho 轨迹
    contribs = []
    ess_by_t = {}
    max_week = max((len(t) for t in trajectories), default=0)
    rho_matrix = []
    for traj in trajectories:
        if not traj:
            continue
        row0 = traj[0]
        dist0 = target_pi(row0, policy)
        v0 = sum(p * _q_lookup(q_pipe, a_pipe, g_pipe, state_key(row0), a,
                               row0["qualified"], "reward") for a, p in dist0.items())
        rho = 1.0
        total = v0
        rhos = []
        for i, row in enumerate(traj):
            # 该步的目标分布与 logging 动作的 pi/mu
            dist = target_pi(row, policy)
            pi_logged = dist.get(row["action"], 0.0)
            mu = row["propensity"] if row["propensity"] > 0 else 0.0
            step = (pi_logged / mu) if mu > 0 else 0.0
            rho = rho * step
            rhos.append(rho)
            if rho == 0.0:
                break
            nxt = traj[i + 1] if i + 1 < len(traj) else None
            if nxt is None:
                v_next = 0.0
            else:
                dist_n = target_pi(nxt, policy)
                v_next = sum(p * _q_lookup(q_pipe, a_pipe, g_pipe, state_key(nxt), a,
                                           nxt["qualified"], "reward") for a, p in dist_n.items())
            q_t = _q_lookup(q_pipe, a_pipe, g_pipe, state_key(row), row["action"],
                            row["qualified"], "reward")
            total += rho * (row["reward"] + v_next - q_t)
        contribs.append(total)
        rho_matrix.append(rhos)
    # ESS：对每个周 t，用 rho_t 的分布计算 (sum rho)^2 / sum rho^2
    ess = {}
    for t in range(max_week):
        vals = [r[t] for r in rho_matrix if len(r) > t]
        if vals:
            s1 = sum(vals)
            s2 = sum(v * v for v in vals)
            ess[t] = (s1 * s1 / s2) if s2 > 0 else 0.0
    # 自助标准误
    rng = random.Random(12345)
    boots = []
    n = len(contribs)
    if n:
        for _ in range(500):
            sample = [contribs[rng.randrange(n)] for _ in range(n)]
            boots.append(statistics.mean(sample))
        se = statistics.stdev(boots) if len(boots) > 1 else 0.0
    else:
        se = 0.0
    return {"DR_pipeline_per_account": statistics.mean(contribs) if contribs else 0.0,
            "DR_se_bootstrap": se, "ESS_by_week": ess,
            "n_trajectories": n,
            "ess_week7": ess.get(7, 0.0), "ess_week15": ess.get(15, 0.0),
            "ess_week23": ess.get(23, 0.0)}


def cross_fitted_dr(trajectories, policy: str):
    """2 折交叉拟合 DR：A 折拟合 Q、评估 B 折，反之亦然，结果按轨迹数加权平均。"""
    by_fold = {0: [], 1: []}
    for traj in trajectories:
        if traj:
            by_fold[traj[0]["account_id"] % 2].append(traj)
    vals, ses, ns = [], [], []
    for fit_fold, eval_fold in [(0, 1), (1, 0)]:
        fit_trajs, eval_trajs = by_fold[fit_fold], by_fold[eval_fold]
        if not fit_trajs or not eval_trajs:
            continue
        q_pipe = fit_q_fqe(fit_trajs, policy, "reward")
        q_trust = fit_q_fqe(fit_trajs, policy, "trust_cost")
        dr = sequential_dr(eval_trajs, policy, q_pipe, q_trust)
        vals.append(dr["DR_pipeline_per_account"] * len(eval_trajs))
        ns.append(len(eval_trajs))
    n = sum(ns) or 1
    return {"DR_pipeline_per_account": sum(vals) / n, "n_trajectories": n}


# ---------------------------------------------------------------- Rosenbaum（Wilcoxon 符号秩 Gamma 界）

def wilcoxon_gamma_bound(diffs, gamma_grid=(1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0)):
    """对配对差分 diffs（正数表示有门/目标优于对照），计算 Rosenbaum Gamma 界：
    在未观测混杂强度为 Gamma 时，每对为正的概率至多为 Gamma/(1+Gamma)；
    最坏情况下单侧 p 值上界 = 在 p=Gamma/(1+Gamma) 的独立 Bernoulli 下，
    加权秩和 T >= 观测 T 的概率（DP 精确计算，零差分对排除）。
    返回：观测 T、Gamma=1 时的 p（即通常的符号秩零假设 p）、
    使 p_upper > 0.05 的最小 Gamma（若 Gamma=1 已 >0.05，返回 'already_nonsignificant'）。"""
    pairs = [(abs(d), 1 if d > 0 else 0) for d in diffs if d != 0]
    if not pairs:
        return {"T_obs": 0, "n_pairs": 0, "p_gamma1": 1.0, "gamma_threshold": None}
    # 平均秩（处理并列绝对值）
    sorted_abs = sorted(a for a, _ in pairs)
    rank_of = {}
    i = 0
    while i < len(sorted_abs):
        j = i
        while j + 1 < len(sorted_abs) and sorted_abs[j + 1] == sorted_abs[i]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # 1-based 平均秩
        for k in range(i, j + 1):
            rank_of[sorted_abs[k]] = avg_rank
        i = j + 1
    ranks = [rank_of[a] for a, _ in pairs]
    signs = [s for _, s in pairs]
    t_obs = sum(r for r, s in zip(ranks, signs) if s == 1)
    # DP：dp[sum] 在整数秩下精确；若有 .5 平均秩，乘 2 转整数
    scale = 2
    ranks_i = [int(round(r * scale)) for r in ranks]
    t_obs_i = int(round(t_obs * scale))
    max_sum = sum(ranks_i)
    out = {}
    for gamma in gamma_grid:
        p = gamma / (1 + gamma)
        dp = [0.0] * (max_sum + 1)
        dp[0] = 1.0
        for ri in ranks_i:
            ndp = [0.0] * (max_sum + 1)
            for s, prob in enumerate(dp):
                if prob == 0:
                    continue
                ndp[s] += prob * (1 - p)
                if s + ri <= max_sum:
                    ndp[s + ri] += prob * p
            dp = ndp
        p_upper = sum(dp[s] for s in range(t_obs_i, max_sum + 1))
        out[gamma] = p_upper
    p1 = out[1.0]
    threshold = None
    for gamma in gamma_grid:
        if out[gamma] > 0.05:
            threshold = gamma
            break
    if threshold == 1.0:
        threshold = "already_nonsignificant_at_gamma1"
    return {"T_obs": t_obs, "n_pairs": len(pairs), "p_gamma1": p1,
            "p_upper_by_gamma": out, "gamma_threshold": threshold}
