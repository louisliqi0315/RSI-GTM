"""Phase 2b 缺口 1：产量门槛 + 帕累托前沿。

规则（写进排名逻辑，不是事后筛选）：
- 只有绝对管道 pipeline >= floor_pipeline 且合格数 qualified_count >= floor_qualified
  的基线才参与主指标 Pipeline-per-Trust 排名；未达标者标记为 INELIGIBLE，
  无论比率多高都不取胜。
- 帕累托前沿：在 (pipeline, pipeline_per_trust) 二维上取最大化非支配点集；
  前沿点不一定是“主指标第一”，它回答的是“在不牺牲产量的前提下，单位信任
  效率最高的那组策略”。
- 门槛敏感性：报告 floor 在 [0, 100, 200, 300, 400, 500] 下的合格集与冠军变化。
  门槛值本身是方法论选择，必须在论文方法节论证，不得事后挑对自己有利的数。

全部输入均为合成数据结果，不得解读为真实厂商表现。
"""
from __future__ import annotations

from typing import Dict, List, Tuple

FLOORS = [0, 100, 200, 300, 400, 500]


def eligible(results: Dict[str, Dict], floor_pipeline: float,
             floor_qualified: int = 0) -> Dict[str, Dict]:
    out = {}
    for name, r in results.items():
        if r["pipeline"] >= floor_pipeline and r["qualified_count"] >= floor_qualified:
            out[name] = r
    return out


def ranked(results: Dict[str, Dict], floor_pipeline: float = 200,
           floor_qualified: int = 0) -> List[Tuple[str, float, float]]:
    """返回 (基线, 主指标, 绝对管道)，按主指标降序，仅含达标者。"""
    elig = eligible(results, floor_pipeline, floor_qualified)
    rows = [(n, r["pipeline_per_trust"], r["pipeline"]) for n, r in elig.items()]
    return sorted(rows, key=lambda x: -x[1])


def pareto_frontier(results: Dict[str, Dict]) -> List[Tuple[str, float, float]]:
    """(pipeline, pipeline_per_trust) 最大化非支配前沿；不设门槛，前沿本身会暴露
    “高比率低产量”点（如 WAIT-heavy）与“高产量低效率”点（如回复率贪心）。"""
    pts = [(n, r["pipeline"], r["pipeline_per_trust"]) for n, r in results.items()]
    front = []
    for n, p, e in pts:
        dominated = any((p2 >= p and e2 >= e) and (p2 > p or e2 > e)
                        for n2, p2, e2 in pts if n2 != n)
        if not dominated:
            front.append((n, p, e))
    return sorted(front, key=lambda x: -x[1])


def floor_sensitivity(results: Dict[str, Dict]) -> List[Dict]:
    rows = []
    for f in FLOORS:
        rk = ranked(results, floor_pipeline=f)
        rows.append({
            "floor_pipeline": f,
            "eligible": [n for n, _, _ in rk],
            "winner": rk[0][0] if rk else None,
            "winner_pipeline_per_trust": rk[0][1] if rk else None,
        })
    return rows


def floor_sensitivity_aggregated(per_seed_results: Dict[int, Dict]) -> List[Dict]:
    """多种子下的门槛敏感性：每个门槛下，各基线“达标率”与“夺冠率”。"""
    rows = []
    for f in FLOORS:
        elig_rate, win_rate = {}, {}
        n = len(per_seed_results)
        for seed, results in per_seed_results.items():
            rk = ranked(results, floor_pipeline=f)
            for name in results:
                elig_rate[name] = elig_rate.get(name, 0) + (1 if name in [x[0] for x in rk] else 0)
            if rk:
                win_rate[rk[0][0]] = win_rate.get(rk[0][0], 0) + 1
        rows.append({
            "floor_pipeline": f,
            "eligible_rate": {k: round(v / n, 3) for k, v in elig_rate.items()},
            "win_rate": {k: round(v / n, 3) for k, v in win_rate.items()},
        })
    return rows
