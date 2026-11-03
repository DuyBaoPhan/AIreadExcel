"""
FastAPI Main Application - REST API cho Excel Rule Engine.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.command_parser import parse_command, ParsedCommand
from app.core.intent_router import Intent
from app.core.response_generator import (
    generate_intent_display,
    generate_workflow_display,
    generate_success_message,
    generate_error_message,
    generate_help,
)
from app.database.db import init_db
from app.database.task_repository import (
    create_task, update_task_status, list_tasks, ensure_session,
)
from app.services.file_manager import (
    get_input_dir, get_output_dir, list_excel_files, file_info, set_projects_root,
)
from app.workflows.aggregation import run_aggregation
from app.workflows.filtering import run_filter
from app.workflows.comparison import run_comparison, get_primary_key_suggestions
from app.workflows.report_export import run_export_report

# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Đặt projects root
_BASE_DIR = Path(__file__).resolve().parent.parent
set_projects_root(_BASE_DIR / "projects")

app = FastAPI(
    title="Excel Rule Engine API",
    description="Rule-based Python Excel AI System — không dùng LLM",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("Excel Rule Engine API started.")


# ──────────────────────────────────────────────────────────────
#  Request / Response Models
# ──────────────────────────────────────────────────────────────

class CommandRequest(BaseModel):
    text: str
    session_id: str | None = None
    project: str = "demo_project"


class CommandResponse(BaseModel):
    session_id: str
    task_id: int | None
    intent_display: str
    workflow_display: str
    parsed: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    requires_input: dict[str, Any] | None = None  # cho multi-turn


class ExecuteFilterRequest(BaseModel):
    session_id: str
    task_id: int
    project: str = "demo_project"
    column: str
    operator: str
    value: Any


class ExecuteComparisonRequest(BaseModel):
    session_id: str
    task_id: int
    project: str = "demo_project"
    primary_key: str
    root_file: str | None = None
    update_file: str | None = None
    treat_as_full_snapshot: bool = False


# ──────────────────────────────────────────────────────────────
#  Endpoints
# ──────────────────────────────────────────────────────────────

@app.post("/api/command", response_model=CommandResponse)
async def handle_command(req: CommandRequest) -> CommandResponse:
    """Nhận câu lệnh tự nhiên, phân tích và thực thi workflow."""
    session_id = req.session_id or str(uuid.uuid4())
    ensure_session(session_id, req.project)

    parsed: ParsedCommand = parse_command(req.text)

    task_id = create_task(session_id, parsed.intent, req.text)

    intent_disp = generate_intent_display(parsed)
    workflow_disp = generate_workflow_display(parsed)

    from app.core.analytical_request import is_analytical_request
    if is_analytical_request(req.text) and parsed.intent != "DELETE":
        from app.services.conversation_reporting import preview_request
        try:
            plan = preview_request(get_input_dir(req.project), req.text)
            update_task_status(task_id, "pending")
            return CommandResponse(
                session_id=session_id, task_id=task_id,
                intent_display="Report planner", workflow_display="Preview and confirm",
                parsed={"intent": "EXPORT", "raw_text": req.text, "parameters": {"report_type": "planned"}},
                requires_input={"type": "report_plan", "text": req.text, "project": req.project, **plan},
            )
        except ValueError as exc:
            update_task_status(task_id, "failed", error_msg=str(exc))
            return CommandResponse(session_id=session_id, task_id=task_id,
                                   intent_display="Report planner", workflow_display="Needs clarification",
                                   parsed=parsed.to_dict(), error=str(exc))

    # Trường hợp không nhận diện được
    if parsed.intent == Intent.UNKNOWN or parsed.error_message:
        update_task_status(task_id, "failed", error_msg=parsed.error_message)
        return CommandResponse(
            session_id=session_id,
            task_id=task_id,
            intent_display=intent_disp,
            workflow_display=workflow_disp,
            parsed=parsed.to_dict(),
            error=parsed.error_message,
        )

    # HELP
    if parsed.intent == "HELP":
        update_task_status(task_id, "done")
        return CommandResponse(
            session_id=session_id,
            task_id=task_id,
            intent_display=intent_disp,
            workflow_display=workflow_disp,
            parsed=parsed.to_dict(),
            result={"help_text": generate_help()},
        )

    # DELETE → yêu cầu xác nhận nhưng không thực hiện
    if parsed.intent == "DELETE":
        update_task_status(task_id, "blocked", error_msg="DELETE blocked")
        return CommandResponse(
            session_id=session_id,
            task_id=task_id,
            intent_display=intent_disp,
            workflow_display=workflow_disp,
            parsed=parsed.to_dict(),
            error=parsed.error_message,
        )

    # Thực thi workflow
    try:
        result = await _execute_workflow(parsed, req.project, session_id, task_id)
        return CommandResponse(
            session_id=session_id,
            task_id=task_id,
            intent_display=intent_disp,
            workflow_display=workflow_disp,
            parsed=parsed.to_dict(),
            result=result.get("result"),
            requires_input=result.get("requires_input"),
        )
    except Exception as exc:
        logger.exception("Workflow error: %s", exc)
        update_task_status(task_id, "failed", error_msg=str(exc))
        return CommandResponse(
            session_id=session_id,
            task_id=task_id,
            intent_display=intent_disp,
            workflow_display=workflow_disp,
            parsed=parsed.to_dict(),
            error=str(exc),
        )


async def _execute_workflow(
    parsed: ParsedCommand,
    project: str,
    session_id: str,
    task_id: int,
) -> dict[str, Any]:
    """Điều phối workflow dựa trên intent."""
    params = parsed.parameters
    input_dir = get_input_dir(project)

    if parsed.intent == "AGGREGATION":
        result = run_aggregation(
            input_dir=input_dir,
            project_name=project,
            specific_files=params.get("specific_files", []),
        )
        update_task_status(task_id, "done", result_path=result["output_path"])
        return {"result": result}

    if parsed.intent == "FILTER":
        column = params.get("column")
        operator = params.get("operator")
        value = params.get("value")

        if not all([column, operator, value is not None]):
            return {
                "requires_input": {
                    "type": "filter_params",
                    "missing": {
                        "column": column is None,
                        "operator": operator is None,
                        "value": value is None,
                    },
                    "message": parsed.error_message or "Thiếu thông tin để lọc.",
                }
            }

        result = run_filter(
            input_dir=input_dir,
            project_name=project,
            column=column,
            operator=operator,
            value=value,
        )
        update_task_status(task_id, "done", result_path=result["output_path"])
        return {"result": result}

    if parsed.intent == "COMPARISON":
        file_names = params.get("file_names", [])
        root_file = next((f for f in file_names if "root" in f.lower()), None)
        update_file = next((f for f in file_names if "update" in f.lower()), None)

        # Yêu cầu primary key
        suggestions = get_primary_key_suggestions(input_dir)
        return {
            "requires_input": {
                "type": "primary_key",
                "suggestions": suggestions,
                "root_file": root_file,
                "update_file": update_file,
                "task_id": task_id,
                "message": (
                    "Vui lòng xác định Primary Key để so sánh. "
                    f"Gợi ý: {suggestions if suggestions else ['employee_id', 'id']}"
                ),
            }
        }

    if parsed.intent == "EXPORT":
        if params.get("report_type") == "revenue":
            from app.workflows.revenue_report import run_revenue_request
            result = run_revenue_request(input_dir, project, parsed.raw_text)
        else:
            result = run_export_report(input_dir=input_dir, project_name=project)
        update_task_status(task_id, "done", result_path=result["output_path"])
        return {"result": result}

    if parsed.intent == "FILE_LIST":
        folder = params.get("folder", "input")
        target_dir = input_dir if folder == "input" else get_output_dir(project)
        files = list_excel_files(target_dir)
        file_details = [file_info(f) for f in files]
        update_task_status(task_id, "done")
        return {
            "result": {
                "files": [f["name"] for f in file_details],
                "file_details": file_details,
                "folder": str(target_dir),
            }
        }

    raise ValueError(f"Không có workflow cho intent: {parsed.intent}")


@app.post("/api/execute/comparison", response_model=CommandResponse)
async def execute_comparison(req: ExecuteComparisonRequest) -> CommandResponse:
    """Thực thi comparison sau khi người dùng cung cấp primary key."""
    input_dir = get_input_dir(req.project)
    try:
        result = run_comparison(
            input_dir=input_dir,
            project_name=req.project,
            primary_key=req.primary_key,
            root_file=req.root_file,
            update_file=req.update_file,
            treat_as_full_snapshot=req.treat_as_full_snapshot,
        )
        update_task_status(req.task_id, "done", result_path=result["output_path"])
        return CommandResponse(
            session_id=req.session_id,
            task_id=req.task_id,
            intent_display="📊 So sánh dữ liệu",
            workflow_display="Comparison Workflow",
            parsed={},
            result=result,
        )
    except Exception as exc:
        update_task_status(req.task_id, "failed", error_msg=str(exc))
        return CommandResponse(
            session_id=req.session_id,
            task_id=req.task_id,
            intent_display="📊 So sánh dữ liệu",
            workflow_display="Comparison Workflow",
            parsed={},
            error=str(exc),
        )


@app.get("/api/files")
async def get_files(
    project: str = Query(default="demo_project"),
    folder: str = Query(default="input"),
):
    """Liệt kê file Excel trong project."""
    target_dir = get_input_dir(project) if folder == "input" else get_output_dir(project)
    files = list_excel_files(target_dir)
    return {
        "folder": str(target_dir),
        "files": [file_info(f) for f in files],
    }


@app.get("/api/download/{project}/{filename}")
async def download_file(project: str, filename: str):
    """Tải file output."""
    output_dir = get_output_dir(project)
    # Kiểm tra path traversal
    try:
        from app.services.file_manager import _safe_resolve
        file_path = _safe_resolve(output_dir, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File không tồn tại: {filename}")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/tasks/{session_id}")
async def get_tasks(session_id: str):
    """Lấy lịch sử tác vụ của session."""
    return {"tasks": list_tasks(session_id)}


@app.get("/")
async def root():
    return {
        "system": "Excel Rule Engine API (Rule-based NLP, No LLM)",
        "status": "running",
        "chatbot_ui": "http://localhost:8501",
        "docs": "http://localhost:8000/docs"
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Excel Rule Engine"}


if __name__ == "__main__":
    import subprocess
    import sys
    import time
    import uvicorn

    print("\n" + "=" * 55)
    print("   KHỞI ĐỘNG EXCEL RULE ENGINE SYSTEM")
    print("=" * 55)

    chatbot_script = Path(__file__).resolve().parent / "chatbot.py"
    
    # Khởi động Streamlit Chatbot chạy ngầm song song
    streamlit_cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(chatbot_script),
        "--server.port=8501",
        "--server.headless=false",
    ]
    
    print("[1/2] Đang khởi động Streamlit Chatbot (Giao diện web)...")
    st_process = subprocess.Popen(streamlit_cmd)
    
    time.sleep(1)
    print("[2/2] Đang khởi động FastAPI Backend Server...")
    print(" -> Giao diện Chatbot: http://localhost:8501")
    print(" -> API Swagger Docs:  http://localhost:8000/docs")
    print("=" * 55 + "\n")

    try:
        # Chạy Uvicorn trực tiếp
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
    finally:
        st_process.terminate()




class ReportPlanRequest(BaseModel):
    text: str
    project: str = "demo_project"
    source_name: str | None = None


class ConfirmReportRequest(ReportPlanRequest):
    fingerprint: str


@app.post("/api/report/preview")
async def preview_conversation_report(req: ReportPlanRequest):
    """Inspect an explicit source selection; never generate an output here."""
    from app.services.conversation_reporting import preview_request
    try:
        return preview_request(get_input_dir(req.project), req.text, req.source_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/report/confirm")
async def confirm_conversation_report(req: ConfirmReportRequest):
    """Rebuild and validate the approved plan against current source bytes."""
    from app.services.conversation_reporting import execute_request
    try:
        return {"result": execute_request(get_input_dir(req.project), req.project, req.text,
                                          req.source_name, req.fingerprint)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
