"""独立于闭式解的参考实现：小步长 RK4 积分 dT/dt=(T_env-T)/tau。

仅用于测试中交叉核验生产代码的解析解，生产裁决路径不含任何数值步进。
"""
from __future__ import annotations

import math


def _ambient_linear(a, c, t_start, dur):
    def env(tt):
        return a + (c - a) * (tt - t_start) / dur

    return env


def _rk4_step(T, t, h, env, tau):
    k1 = (env(t) - T) / tau
    k2 = (env(t + h / 2) - (T + h * k1 / 2)) / tau
    k3 = (env(t + h / 2) - (T + h * k2 / 2)) / tau
    k4 = (env(t + h) - (T + h * k3)) / tau
    return T + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6


def rk4_simulate(records, tau_closed, tau_open, dt=0.25):
    """以 records 的 box_temp[0] 为初值，按各段 lid_open 选 tau 向前积分。

    返回逐 dt 的 (t, T) 列表，段长非整数倍 dt 时尾部补齐到端点。
    """
    out = []
    T = float(records[0]["box_temp"])
    t = float(records[0]["time"])
    out.append((t, T))
    for i in range(len(records) - 1):
        r0, r1 = records[i], records[i + 1]
        dur = float(r1["time"]) - float(r0["time"])
        env = _ambient_linear(float(r0["ambient_temp"]), float(r1["ambient_temp"]), t, dur)
        tau = float(tau_open if r0["lid_open"] else tau_closed)

        n = int(math.floor(dur / dt))
        for k in range(n):
            h = min(dt, dur - k * dt)
            T = _rk4_step(T, t, h, env, tau)
            t += h
            out.append((t, T))
        if t < float(r1["time"]) - 1e-9:
            h = float(r1["time"]) - t
            if h > 1e-12:
                T = _rk4_step(T, t, h, env, tau)
                t = float(r1["time"])
                out.append((t, T))
    return out


def make_records_from_sim(times, ambients, lid, t0_box, tau_closed, tau_open):
    """给定每时刻环境温/箱盖，用 RK4 生成与模型自洽的箱温记录。"""
    raw = [
        {"time": times[0], "box_temp": t0_box, "ambient_temp": ambients[0], "lid_open": lid[0]}
    ]
    T = t0_box
    t = float(times[0])
    dt = 0.1
    for i in range(len(times) - 1):
        dur = float(times[i + 1]) - float(times[i])
        env = _ambient_linear(ambients[i], ambients[i + 1], t, dur)
        tau = float(tau_open if lid[i] else tau_closed)
        n = int(round(dur / dt))
        for _ in range(n):
            T = _rk4_step(T, t, dt, env, tau)
            t += dt
        raw.append(
            {
                "time": times[i + 1],
                "box_temp": T,
                "ambient_temp": ambients[i + 1],
                "lid_open": lid[i + 1],
            }
        )
    return raw


def box_closed_form_segment(records, i, tau_closed, tau_open):
    """返回第 i 段箱温闭式解 T_box(s)（s 距段起点），与生产引擎完全同构。"""
    import math as _m

    r0, r1 = records[i], records[i + 1]
    dur = float(r1["time"]) - float(r0["time"])
    a = float(r0["ambient_temp"])
    b = (float(r1["ambient_temp"]) - a) / dur
    tau = float(tau_open if r0["lid_open"] else tau_closed)
    t_i = float(r0["box_temp"])

    def box(s):
        return a + b * (s - tau) + (t_i - a + b * tau) * _m.exp(-s / tau)

    return box, dur


def rk4_core_simulate(records, tau_closed, tau_open, tau_sample, core_initial, dt=0.25):
    """独立 RK4 积分样品核心温度 dC/dt=(T_box(t)-C)/tau_sample。

    驱动 T_box 取生产箱温求解的逐段闭式连续曲线（每段以该段实测箱温锚定，
    与生产 audit 的箱体口径一致）；核心温度 C 跨记录连续，仅以 core_initial
    在首条记录锚定一次。用于交叉核验闭式核心求解，不参与生产裁决。
    返回逐 dt 的 (t, C, T_box)。
    """

    def rk4_core(C, t, h, box_fn, tau_s):
        def f(tt, cc):
            return (box_fn(tt) - cc) / tau_s

        k1 = f(t, C)
        k2 = f(t + h / 2, C + h * k1 / 2)
        k3 = f(t + h / 2, C + h * k2 / 2)
        k4 = f(t + h, C + h * k3)
        return C + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6

    out = []
    C = float(core_initial)
    t = float(records[0]["time"])
    box0, _ = box_closed_form_segment(records, 0, tau_closed, tau_open)
    out.append((t, C, box0(0.0)))
    for i in range(len(records) - 1):
        box, dur = box_closed_form_segment(records, i, tau_closed, tau_open)
        seg_t0 = float(records[i]["time"])
        n = int(math.floor(dur / dt))
        for k in range(n):
            h = min(dt, dur - k * dt)
            C = rk4_core(C, t, h, lambda tt, _s0=seg_t0, _bf=box: _bf(tt - _s0), tau_sample)
            t += h
            out.append((t, C, box(t - seg_t0)))
        if t < float(records[i + 1]["time"]) - 1e-9:
            h = float(records[i + 1]["time"]) - t
            C = rk4_core(C, t, h, lambda tt, _s0=seg_t0, _bf=box: _bf(tt - _s0), tau_sample)
            t = float(records[i + 1]["time"])
            out.append((t, C, box(dur)))
    return out
