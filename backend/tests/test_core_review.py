"""核心温度复核引擎测试。

口径：启用 core_review 后，服务端沿用逐段箱温闭式曲线作为样品一阶响应的
连续驱动，核心温度仅在首条记录处锚定一次并跨记录连续传递；必须覆盖
样品热惯性与箱体热惯性相等的退化情形，并连续定位段内极值、阈值穿越与
首个超限时刻。未启用时原请求、结论与证据保持不变。
"""
from __future__ import annotations

import math

import pytest

from app.thermal import ThermalValidationError, audit

from .reference import make_records_from_sim, rk4_core_simulate

TAU_CLOSED = 300.0
TAU_OPEN = 90.0


def box_params(**over):
    base = {
        "tau_closed": TAU_CLOSED,
        "tau_open": TAU_OPEN,
        "box_temp_limit": 8.0,
        "exposure_limit_seconds": 600.0,
    }
    base.update(over)
    return base


def core(**over):
    base = {
        "enabled": True,
        "sample_initial_temp": 4.0,
        "tau_sample_seconds": 600.0,
        "core_temp_limit": 8.0,
    }
    base.update(over)
    return base


def run(records, cr=None, **pover):
    payload = {"records": records, "parameters": box_params(**pover)}
    if cr is not None:
        payload["core_review"] = cr
    return audit(payload)


def spike_records():
    times = [0, 60, 1560, 2460, 3360]
    ambs = [25.0, 25.0, 3.0, 3.0, 3.0]
    return make_records_from_sim(times, ambs, [False] * 5, 4.0, TAU_CLOSED, TAU_OPEN)


# ---------- 未启用：原请求、结论与证据保持不变 ----------

def test_disabled_payload_unchanged():
    recs = spike_records()
    plain = run(recs, exposure_limit_seconds=300)
    assert "core_review" not in plain
    assert "final_status" not in plain and "box_status" not in plain
    assert set(plain["curve"][0]) == {"elapsed_seconds", "time", "box_temp", "ambient_temp", "lid_open"}

    explicit_off = run(recs, {"enabled": False}, exposure_limit_seconds=300)
    assert "core_review" not in explicit_off
    assert explicit_off["status"] == plain["status"]


# ---------- 闭式解 vs 独立 RK4（一般、近相等、严格相等） ----------

@pytest.mark.parametrize("tau_sample", [600.0, 123.456, TAU_CLOSED, TAU_OPEN, 300.0000001])
def test_core_closed_form_matches_rk4(tau_sample):
    times = [0, 600, 1200, 1800, 2400]
    ambs = [25.0, 26.0, 3.0, 20.0, 4.0]
    lids = [False, True, False, True, False]
    recs = make_records_from_sim(times, ambs, lids, 4.0, TAU_CLOSED, TAU_OPEN)
    res = run(recs, core(tau_sample_seconds=tau_sample))

    sim = rk4_core_simulate(recs, TAU_CLOSED, TAU_OPEN, tau_sample, 4.0, dt=0.05)
    for pt in res["curve"][::31]:
        u = pt["elapsed_seconds"]
        for (ta, va), (tb, vb) in zip(sim, sim[1:]):
            if ta - 1e-9 <= u <= tb + 1e-9:
                ref = va + (vb - va) * (u - ta) / (tb - ta)
                assert abs(pt["core_temp"] - ref) < 1e-6, (tau_sample, u, pt["core_temp"], ref)
                break
        else:
            raise AssertionError(f"RK4 未覆盖 t={u}")


def test_equal_tau_is_degenerate_branch_and_continuous():
    recs = spike_records()
    res = run(recs, core(tau_sample_seconds=TAU_CLOSED))
    segs = res["core_review"]["segments"]
    assert all(s["tau_equal"] for s in segs)
    # 跨记录：本段起点核心温必须严格等于上一段段末（连续传递，不重新锚定）
    for prev, nxt in zip(segs, segs[1:]):
        assert nxt["core_temp_start"] == pytest.approx(prev["core_temp_end"], abs=1e-12)
    # 首段以样品录入温度锚定，而非首条箱温读数巧合
    assert segs[0]["core_temp_start"] == 4.0


def test_core_never_reanchored_despite_record_gaps():
    # 人为篡改第 3 条箱温读数（制造 model_record_gap）：核心温度仍由连续
    # 闭式驱动+段末状态传递，段间核心温必须无缝，不在记录点跳变。
    recs = spike_records()
    recs[2] = dict(recs[2], box_temp=0.5)
    res = run(recs, core(tau_sample_seconds=700.0))
    segs = res["core_review"]["segments"]
    for prev, nxt in zip(segs, segs[1:]):
        assert nxt["core_temp_start"] == pytest.approx(prev["core_temp_end"], abs=1e-9)
    assert abs(segs[1]["core_temp_end"] - segs[2]["core_temp_start"]) < 1e-9


# ---------- 连续定位极值、穿越与首个超限时刻 ----------

def test_core_first_risk_is_earliest_upcrossing():
    recs = spike_records()
    res = run(recs, core(tau_sample_seconds=900.0))
    cr = res["core_review"]
    assert cr["status"] == "reject"
    assert cr["first_risk_time"] is not None
    first_up = min(
        c["elapsed_seconds"]
        for s in cr["segments"]
        for c in s["crossings"]
        if c["direction"] == "up"
    )
    assert cr["first_risk_time"]["elapsed_seconds"] == pytest.approx(first_up, abs=1e-6)
    # 首个风险时刻落在第一个连续超限区间起点
    iv0 = cr["exceedance_intervals"][0]
    assert cr["first_risk_time"]["elapsed_seconds"] == pytest.approx(
        iv0["elapsed_start_seconds"], abs=1e-6
    )
    assert cr["first_risk_time"]["interval_index"] == iv0["index"]


def test_core_extrema_and_crossings_against_dense_scan():
    # 先升后降再升的环境温，可在同一核心段内诱导两个驻点。
    times = [0, 1500, 3000, 4500]
    ambs = [25.0, 2.0, 28.0, 3.0]
    lids = [False, True, False, False]
    recs = make_records_from_sim(times, ambs, lids, 4.0, TAU_CLOSED, TAU_OPEN)

    for tau_sample in (800.0, TAU_CLOSED, TAU_OPEN):
        res = run(recs, core(tau_sample_seconds=tau_sample))
        sim = rk4_core_simulate(recs, TAU_CLOSED, TAU_OPEN, tau_sample, 4.0, dt=1.0)
        for seg in res["core_review"]["segments"]:
            lo, hi = seg["elapsed_start_seconds"], seg["elapsed_end_seconds"]
            vals = [v for t, v in sim if lo - 1e-9 <= t <= hi + 1e-9]
            assert seg["max_temp"]["value"] >= max(vals) - 0.02
            assert seg["min_temp"]["value"] <= min(vals) + 0.02


def test_core_intervals_merge_across_records():
    # 核心在记录点两侧均超限：段内碎片须全局并为一个连续区间。
    times = [0, 400, 800, 1200, 1600]
    ambs = [20.0] * 5
    recs = make_records_from_sim(times, ambs, [False] * 5, 4.0, TAU_CLOSED, TAU_OPEN)
    res = run(recs, core(tau_sample_seconds=300.0, core_temp_limit=8.0))
    pieces = sum(len(s["exceedance_intervals"]) for s in res["core_review"]["segments"])
    assert pieces >= 2
    assert len(res["core_review"]["exceedance_intervals"]) == 1


def test_core_pass_when_never_above_limit():
    times = list(range(0, 2401, 300))
    ambs = [3.0, 3.5, 4.0, 3.8, 3.2, 3.0, 2.8, 2.5, 2.0]
    recs = make_records_from_sim(times, ambs, [False] * 9, 4.0, TAU_CLOSED, TAU_OPEN)
    res = run(recs, core(tau_sample_seconds=300.0))
    cr = res["core_review"]
    assert cr["status"] == "pass"
    assert cr["verdict"] == "核心放行"
    assert cr["first_risk_time"] is None
    assert cr["exceedance_intervals"] == []


# ---------- 箱体放行但核心拒收 ----------

def test_box_pass_but_core_reject():
    # 箱温短时冲高但连续暴露不足 3600s → 箱体放行；样品阈值更严（7℃），
    # 热惯性使其越过核心上限 → 核心拒收，最终结论须区分。
    times = [0, 600, 1200, 1800]
    ambs = [4.0, 25.0, 25.0, 4.0]
    recs = make_records_from_sim(times, ambs, [False] * 4, 4.0, TAU_CLOSED, TAU_OPEN)
    res = run(
        recs,
        core(tau_sample_seconds=TAU_CLOSED, core_temp_limit=7.0),
        exposure_limit_seconds=3600,
    )
    assert res["box_status"] == "pass"
    assert res["core_review"]["status"] == "reject"
    assert res["core_review"]["verdict"] == "核心拒收"
    assert res["final_status"] == "reject"
    assert "箱体放行但核心拒收" in res["final_verdict"]
    assert res["box_rejected"] is False and res["core_rejected"] is True


def test_box_reject_but_core_pass():
    # 样品热惯性极大且初温低：箱体已构成超温拒收，核心仍未越限。
    recs = spike_records()
    res = run(
        recs,
        core(tau_sample_seconds=100000.0, core_temp_limit=8.0),
        exposure_limit_seconds=300,
    )
    assert res["box_status"] == "reject"
    assert res["core_review"]["status"] == "pass"
    assert res["final_status"] == "reject"
    assert "箱体与核心" not in res["final_verdict"]


def test_enabled_curve_carries_core_temp():
    res = run(spike_records(), core())
    assert all("core_temp" in p for p in res["curve"])


# ---------- 字段级错误 ----------

@pytest.mark.parametrize(
    "cr,field",
    [
        ({"enabled": True, "sample_initial_temp": float("nan"),
          "tau_sample_seconds": 300, "core_temp_limit": 8}, "core_review.sample_initial_temp"),
        ({"enabled": True, "sample_initial_temp": 4,
          "tau_sample_seconds": float("inf"), "core_temp_limit": 8}, "core_review.tau_sample_seconds"),
        ({"enabled": True, "sample_initial_temp": 4,
          "tau_sample_seconds": 0, "core_temp_limit": 8}, "core_review.tau_sample_seconds"),
        ({"enabled": True, "sample_initial_temp": 4,
          "tau_sample_seconds": -5, "core_temp_limit": 8}, "core_review.tau_sample_seconds"),
        ({"enabled": True, "sample_initial_temp": 4,
          "tau_sample_seconds": 300, "core_temp_limit": float("nan")}, "core_review.core_temp_limit"),
        ({"enabled": True, "sample_initial_temp": 4,
          "tau_sample_seconds": 300}, "core_review.core_temp_limit"),
        ({"enabled": "yes", "sample_initial_temp": 4,
          "tau_sample_seconds": 300, "core_temp_limit": 8}, "core_review.enabled"),
    ],
)
def test_invalid_core_params_field_level(cr, field):
    with pytest.raises(ThermalValidationError) as ei:
        run(spike_records(), cr)
    assert ei.value.field == field
    assert ei.value.code in {"bad_core_param", "bad_core_review"}


def test_core_review_must_be_object():
    with pytest.raises(ThermalValidationError) as ei:
        run(spike_records(), [1, 2, 3])
    assert ei.value.code == "bad_core_review"
    assert ei.value.field == "core_review"
