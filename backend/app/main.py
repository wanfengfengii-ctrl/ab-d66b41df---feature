"""FastAPI 应用：温控审计业务 API、健康检查，生产模式托管前端静态资源。"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .thermal import ThermalValidationError, audit

app = FastAPI(
    title="海上平台油样运输温控审计",
    description="一阶热响应模型解析求解，裁决运输途中连续超温暴露",
    version="1.0.0",
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/audit/schema")
def audit_schema() -> dict[str, object]:
    """返回入参约定，便于前端与冒烟脚本自检。"""
    return {
        "records": "4-30 条，按 time 严格递增；字段 time(ISO8601 或数值纪元秒，全表统一)、"
        "box_temp、ambient_temp(有限数值)、lid_open(布尔，仅在记录时刻起向后生效)",
        "parameters": {
            "tau_closed": "箱盖关闭热惯性时间常数（秒，>0）",
            "tau_open": "箱盖开启热惯性时间常数（秒，>0）",
            "box_temp_limit": "允许箱温阈值（数值，严格超限 T>limit 计暴露）",
            "exposure_limit_seconds": "允许连续暴露时长（秒，>0）",
        },
        "core_temperature_review": {
            "_note": "可选；缺省或 enabled=false 时不启用，原请求/结论/证据保持不变",
            "enabled": "是否启用核心温度复核（布尔；缺省/false/null 视为不启用）",
            "sample_initial_temp": "首条记录时刻的样品温度（有限数值，仅此一次锚定样品状态）",
            "tau_sample_seconds": "样品对箱温的热惯性时间常数（秒，>0；须覆盖等于箱体热惯性的退化情形）",
            "core_temp_limit": "核心温度上限（有限数值，严格超限 C>limit 即核心拒收）",
            "_solver": "启用后以箱体逐段闭式连续曲线为一阶响应驱动，样品状态跨记录连续传递，"
            "不在每条记录处重新锚定，也不按展示采样点裁决；返回段内极值/阈值穿越/首个超限时刻",
        },
    }


@app.post("/api/audit")
async def run_audit(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "status": "invalid",
                "verdict": "数据不合法",
                "errors": [
                    {"code": "bad_json", "message": "请求体不是合法 JSON", "field": None}
                ],
            },
        )
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={
                "status": "invalid",
                "verdict": "数据不合法",
                "errors": [
                    {"code": "bad_body", "message": "请求体必须是 JSON 对象", "field": None}
                ],
            },
        )
    try:
        result = audit(payload)
    except ThermalValidationError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "status": "invalid",
                "verdict": "数据不合法",
                "errors": [exc.to_dict()],
            },
        )
    return JSONResponse(status_code=200, content=result)


# 生产环境：镜像内已完成前端构建，直接托管静态资源
STATIC_DIR = Path(os.environ.get("STATIC_DIR", "/app/frontend/dist"))
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
