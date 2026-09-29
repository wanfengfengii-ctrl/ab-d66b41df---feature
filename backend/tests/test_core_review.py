"""核心温度复核引擎测试。

覆盖：
* 闭式核心解与独立 RK4（以连续箱温闭式曲线为驱动）交叉验证；
* 样品热惯性等于箱体热惯性的退化情形（等 τ 极限闭式解）；
* 样品状态跨记录连续传递、绝不重新锚定；
* 段内极值 / 阈值穿越 / 首个超限时刻的解析定位；
* 箱体放行但核心拒收的结论区分；
* 未启用时原请求、结论与证据完全不变；
* 非法 / 无穷 / 缺失参数的字段级错误。
"""
from __future__ import annotations

import math

import pytest

from app.thermal import ThermalValidationError, audit

from .reference import make_records_from_sim, rk4_core_simulate

TAU_CLOSED = 300.0
TAU_OPEN = 90.0
LIMIT = 8.0
EXPOSURE = 600.0


def params(**over):
    base = {
        "tau_closed": TAU_CLOSED,
        "tau_open": TAU_OPEN,
        "box_temp_limit": LIMIT,
        "exposure_limit_seconds": EXPOSURE,
    }
    base.update(over)
    return base


def review(tau_sample, core_initial, core_limit=LIMIT, enabled=True):
    return {
        "enabled": enabled,
        "sample_initial_temp": core_initial,
        "tau_sample_seconds": tau_sample,
        "core_temp_limit": core_limit,
    }


def run(records, rev=None, **over):
    payload = {"records": records, "parameters": params(**over)}
    if rev is not None:
        payload["core_temperature_review"] = rev
    return audit(payload)


def spike_records():
    times = [0, 60, 1560, 2460, 3360]
    ambs = [25.0, 25.0, 3.0, 3.0, 3.0]
    return make_records_from_sim(times, ambs, [False] * 5, 4.0, TAU_CLOSED, TAU_OPEN)


def interp_sim(sim, u):
    for (ta, ca, ba), (tb, cb, bb) in zip(sim, sim[1:]):
        if ta - 1e-9 <= u <= tb + 1e-9:
            w = (u - ta) / (tb - ta)
            return ca + (cb - ca) * w
    raise AssertionError(f"仿真未覆盖 t={u}")


# ---------- 闭式解与独立 RK4 交叉验证 ----------

@pytest.mark.parametrize("tau_sample", [90.0, 600.0, 300.0])
def test_core_closed_form_matches_independent_rk4(tau_sample):
    recs = spike_records()
    res = run(recs, review(tau_sample, 4.0))
    sim = rk4_core_simulate(recs, TAU_CLOSED, TAU_OPEN, tau_sample, 4.0, dt=0.2)
    curve = res["core_temperature_review"]["curve"]
    for pt in curve[::23]:
        ref = interp_sim(sim, pt["elapsed_seconds"])
        assert abs(pt["core_temp"] - ref) < 2e-5, (tau_sample, pt["elapsed_seconds"], pt["core_temp"], ref)


def test_core_closed_form_matches_rk4_with_lid_switching():
    times = list(range(0, 3601, 600))
    ambs = [25.0, 26.0, 24.5, 27.0, 23.0, 26.5, 24.0]
    lids = [False, True, False, False, True, False, False]
    recs = make_records_from_sim(times, ambs, lids, 20.0, TAU_CLOSED, TAU_OPEN)
    res = run(recs, review(420.0, 20.0))
    sim = rk4_core_simulate(recs, TAU_CLOSED, TAU_OPEN, 420.0, 20.0, dt=0.2)
    curve = res["core_temperature_review"]["curve"]
    for pt in curve[::29]:
        ref = interp_sim(sim, pt["elapsed_seconds"])
        assert abs(pt["core_temp"] - ref) < 2e-5


def test_equal_tau_degenerate_case_matches_rk4_and_limit_formula():
    # 全程箱盖关闭：tau_box == tau_sample == 300，触发等惯性极限闭式解
    recs = spike_records()
    res = run(recs, review(300.0, 4.0))
    cb = res["core_temperature_review"]
    assert all(s["degenerate_equal_tau"] for s in cb["segments"])
    sim = rk4_core_simulate(recs, TAU_CLOSED, TAU_OPEN, 300.0, 4.0, dt=0.1)
    for pt in cb["curve"][::31]:
        ref = interp_sim(sim, pt["elapsed_seconds"])
        assert abs(pt["core_temp"] - ref) < 1e-5
    # 等 τ 公式在 τ_sample 两侧趋于一致（极限连续性）
    near = run(recs, review(300.0 + 1e-4, 4.0))
    for a, b in zip(cb["curve"][::41], near["core_temperature_review"]["curve"][::41]):
        assert abs(a["core_temp"] - b["core_temp"]) < 1e-3


# ---------- 跨记录连续传递、不重新锚定 ----------

def test_core_state_passes_through_records_without_reanchoring():
    recs = spike_records()
    res = run(recs, review(450.0, 4.0))
    segs = res["core_temperature_review"]["segments"]
    # 段末样品状态必须严格等于下一段起点（连续传递）
    for i in range(len(segs) - 1):
        assert segs[i]["core_temp_end"] == pytest.approx(segs[i + 1]["core_temp_start"], abs=1e-12)
    # 即便记录读数与箱温模型值有偏差，样品也只跟随连续箱温曲线：
    # 人为把第 3 条记录箱温改得离谱，核心曲线不应在该点跳变
    tampered = [dict(r) for r in recs]
    tampered[2] = dict(tampered[2], box_temp=-50.0)
    res2 = run(tampered, review(450.0, 4.0))
    s2 = res2["core_temperature_review"]["segments"]
    for i in range(len(s2) - 1):
        assert s2[i]["core_temp_end"] == pytest.approx(s2[i + 1]["core_temp_start"], abs=1e-12)
    # 被篡改记录前后，样品温度无跳变（与未篡改时该时刻状态一致）
    assert s2[1]["core_temp_end"] == pytest.approx(segs[1]["core_temp_end"], abs=1e-9)


def test_core_initial_condition_only_at_first_record():
    recs = spike_records()
    res = run(recs, review(300.0, 11.0))
    first = res["core_temperature_review"]["segments"][0]
    assert first["core_temp_start"] == 11.0
    # 初值高于上限 → 首个风险时刻必须就是首条记录时刻（t=0）
    risk = res["core_temperature_review"]["first_risk_time"]
    assert risk["elapsed_seconds"] == 0.0


# ---------- 段内极值与阈值穿越 ----------

def test_core_interior_extremum_matches_dense_scan():
    recs = spike_records()
    res = run(recs, review(600.0, 4.0))
    cb = res["core_temperature_review"]
    hot = [s for s in cb["segments"] if s["max_temp"]["kind"] == "interior"]
    assert hot, "滞后样品在箱温冲高段应存在段内极大值"
    sim = rk4_core_simulate(recs, TAU_CLOSED, TAU_OPEN, 600.0, 4.0, dt=0.1)
    for seg in hot:
        lo, hi = seg["elapsed_start_seconds"], seg["elapsed_end_seconds"]
        ref_max = max(c for t, c, _ in sim if lo - 1e-9 <= t <= hi + 1e-9)
        assert abs(seg["max_temp"]["value"] - ref_max) < 1e-3
        assert lo < seg["max_temp"]["elapsed_seconds"] < hi


def test_core_up_crossing_root_is_analytically_accurate():
    # 恒温箱温 20℃（模型箱温恒为 20），样品 4℃ 起步：
    # C(s)=20+(4-20)e^{-s/tau}，上穿 8 的时刻可手工求得
    Tbox, C0, tau_s, lim = 20.0, 4.0, 300.0, 8.0
    recs = [
        {"time": i * 900, "box_temp": Tbox, "ambient_temp": Tbox, "lid_open": False}
        for i in range(4)
    ]
    res = run(recs, review(tau_s, C0, lim))
    crossings = [c for s in res["core_temperature_review"]["segments"] for c in s["crossings"]]
    up = [c for c in crossings if c["direction"] == "up"]
    assert len(up) == 1
    expect = -tau_s * math.log((lim - Tbox) / (C0 - Tbox))
    assert abs(up[0]["elapsed_seconds"] - expect) < 1e-6
    risk = res["core_temperature_review"]["first_risk_time"]
    assert abs(risk["elapsed_seconds"] - expect) < 1e-6


def test_core_down_crossing_closes_interval():
    # 样品热起步 15℃，箱温恒 4℃，下穿 6℃ 后不再超限：得到一个有限超温区间
    Tbox, C0, tau_s, lim = 4.0, 15.0, 300.0, 6.0
    recs = [
        {"time": i * 900, "box_temp": Tbox, "ambient_temp": Tbox, "lid_open": False}
        for i in range(4)
    ]
    res = run(recs, review(tau_s, C0, lim))
    cb = res["core_temperature_review"]
    assert cb["status"] == "reject"
    assert len(cb["exceedance_intervals"]) == 1
    iv = cb["exceedance_intervals"][0]
    assert iv["elapsed_start_seconds"] == 0.0
    expect = -tau_s * math.log((lim - Tbox) / (C0 - Tbox))
    assert abs(iv["elapsed_end_seconds"] - expect) < 1e-6
    dirs = [c["direction"] for s in cb["segments"] for c in s["crossings"]]
    assert dirs == ["down"]


def test_core_verdict_does_not_use_display_samples():
    # 阈值穿越点刻意不落在展示采样网格（每段 48 等分）上
    Tbox, C0, tau_s, lim = 20.0, 4.0, 300.0, 8.0
    recs = [
        {"time": i * 1000, "box_temp": Tbox, "ambient_temp": Tbox, "lid_open": False}
        for i in range(4)
    ]
    res = run(recs, review(tau_s, C0, lim))
    risk = res["core_temperature_review"]["first_risk_time"]["elapsed_seconds"]
    grid = {1000 * k / 48 for k in range(48 * 3 + 1)}
    assert all(abs(risk - g) > 1e-9 for g in grid)


# ---------- 箱体放行但核心拒收 ----------

def test_segment_with_two_interior_stationary_points():
    # 箱温谷底场景（T0=20，环境 2→25）：滞后样品在同一段内先出现内部极大、
    # 再出现内部极小（两个解析驻点），随后随箱温爬升再次上穿。
    recs = [
        {"time": 0, "box_temp": 20.0, "ambient_temp": 2.0, "lid_open": False},
        {"time": 1, "box_temp": 20.0, "ambient_temp": 2.0, "lid_open": False},
        {"time": 1501, "box_temp": 20.0, "ambient_temp": 25.0, "lid_open": False},
        {"time": 3001, "box_temp": 20.0, "ambient_temp": 25.0, "lid_open": False},
    ]
    res = run(recs, review(300.0, 10.0, core_limit=12.0))
    seg = res["core_temperature_review"]["segments"][1]
    # 该段内核心先升后降再升：两次上穿夹一次下穿，两个超温子区间，
    # 结构上要求切出两个内部驻点（先峰后谷），单驻点切分必然漏掉一个穿越。
    assert seg["max_temp"]["kind"] in ("interior", "end")
    dirs = [c["direction"] for c in seg["crossings"]]
    assert dirs == ["up", "down", "up"]
    assert len(seg["exceedance_intervals"]) == 2
    # 与稠密积分的段内最大/最小核对（段内全局极值同样取自驻点+端点）
    sim = rk4_core_simulate(recs, TAU_CLOSED, TAU_OPEN, 300.0, 10.0, dt=0.1)
    lo, hi = seg["elapsed_start_seconds"], seg["elapsed_end_seconds"]
    ref_max = max(c for t, c, _ in sim if lo <= t <= hi)
    ref_min = min(c for t, c, _ in sim if lo <= t <= hi)
    assert abs(seg["max_temp"]["value"] - ref_max) < 1e-2
    assert abs(seg["min_temp"]["value"] - ref_min) < 1e-2


def test_box_pass_but_core_reject_is_distinguished():
    # 箱温记录全程低于 8℃（探头合格），箱温裁决放行；
    # 样品热惯性大、核心初始偏冷跟随 7.5℃ 箱温，核心上限设 6℃ → 核心超限
    times = [0, 600, 1200, 1800, 2400]
    recs = [
        {"time": t, "box_temp": 7.5 - 3.5 * math.exp(-t / 300.0),
         "ambient_temp": 7.5, "lid_open": False}
        for t in times
    ]
    assert all(r["box_temp"] < LIMIT for r in recs)
    res = run(recs, review(900.0, 4.0, core_limit=6.0))
    assert res["box_status"] == "pass"
    assert res["status"] == "reject"
    cb = res["core_temperature_review"]
    assert cb["status"] == "reject"
    assert "核心" in res["verdict"]
    assert cb["first_risk_time"] is not None


def test_box_reject_and_core_pass_reports_combined_verdict():
    recs = spike_records()
    # 样品初值已足够冷且热惯性极大，核心追不上箱温短时冲高；上限放宽到 15℃
    res = run(recs, review(1.0e9, 4.0, core_limit=15.0))
    assert res["box_status"] == "reject"
    assert res["status"] == "reject"
    assert res["core_temperature_review"]["status"] == "pass"
    assert res["core_temperature_review"]["first_risk_time"] is None


# ---------- 未启用：原请求/结论/证据保持不变 ----------

def test_disabled_review_leaves_response_untouched():
    recs = spike_records()
    plain = run(recs)
    # 缺省键
    assert "core_temperature_review" not in plain
    assert "box_status" not in plain and "box_verdict" not in plain
    # 显式 enabled=false（即便附带垃圾字段）与缺省请求【完全一致】
    explicit = run(recs, {"enabled": False, "tau_sample_seconds": "oops"})
    assert explicit == plain
    # enabled=null 等同未启用
    none_rev = run(recs, {"enabled": None})
    assert none_rev == plain


# ---------- 字段级数据合法性 ----------

def test_bad_core_review_params_are_field_level_422():
    recs = spike_records()
    bad_payloads = [
        (review(300.0, 4.0) | {"enabled": "yes"}, "core_temperature_review.enabled"),
        (review(300.0, 4.0) | {"sample_initial_temp": float("nan")},
         "core_temperature_review.sample_initial_temp"),
        (review(300.0, 4.0) | {"sample_initial_temp": float("inf")},
         "core_temperature_review.sample_initial_temp"),
        (review(300.0, 4.0) | {"tau_sample_seconds": float("-inf")},
         "core_temperature_review.tau_sample_seconds"),
        (review(300.0, 4.0) | {"tau_sample_seconds": 0},
         "core_temperature_review.tau_sample_seconds"),
        (review(300.0, 4.0) | {"tau_sample_seconds": -1},
         "core_temperature_review.tau_sample_seconds"),
        (review(300.0, 4.0) | {"core_temp_limit": float("nan")},
         "core_temperature_review.core_temp_limit"),
        ({"enabled": True, "tau_sample_seconds": 300, "core_temp_limit": 8},
         "core_temperature_review.sample_initial_temp"),
    ]
    for rev, field in bad_payloads:
        with pytest.raises(ThermalValidationError) as ei:
            run(recs, rev)
        assert ei.value.code == "bad_core_review"
        assert ei.value.field == field
    with pytest.raises(ThermalValidationError) as ei:
        run(recs, "not-an-object")
    assert ei.value.field == "core_temperature_review"
