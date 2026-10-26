"""
Phase 2g — 工作流-only 有门 vs 静态 G，大功效预注册检验（新文件，不改动旧文件）

合成数据声明：全部机制均为合成假设，不是真实厂商数据，不宣称真实
转化率、收入、厂商表现或跨厂商泛化。

口径保证（刻意不重写仿真逻辑）：本文件直接复用 phase2f_sim.run_arm_f，
因此 W 与 STATIC 的定义、门容忍、验证集口径、候选生成与 2f 逐项一致。
任何参数漂移都会在一致性锚点上暴露：W 的空比较种子上 W 与 STATIC 的
真值必须逐种子完全相等；若不成立，本实验作废。
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from phase2f_sim import run_arm_f  # noqa: F401  (2f 口径，定义完全一致)

__all__ = ["run_arm_f"]
