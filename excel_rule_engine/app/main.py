"""
FastAPI Main Application - REST API cho Excel Rule Engine.
"""

from __future__ import annotations

from app.paths import PROJECTS_DIR
from app.services.runtime.environment import load_environment
load_environment()

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.database.db import init_db
from app.database.task_repository import (
    create_task, update_task_status, list_tasks, ensure_session,
)
from app.services.sources.file_manager import (
    get_input_dir, get_output_dir, list_excel_files, file_info, set_projects_root,
)
from app.workflows.comparison import run_comparison

# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Đặt projects root
set_projects_root(PROJECTS_DIR)

app = FastAPI(
    title="Excel Rule Engine API",
    description="OpenAI conversational Excel assistant with deterministic data validation",
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
    """AI-only compatibility adapter for legacy command clients."""
    session_id = req.session_id or str(uuid.uuid4())
    ensure_session(session_id, req.project)

    from app.services.ai.planner_settings import planner_mode
    from app.services.chat.chat_conversation import chat
    task_id = create_task(session_id, "CHAT", req.text)
    try:
        planner_mode()  # Reject retired modes; never fall back to local NLP.
        # New /api/chat clients retain their server-issued conversational id.
        outcome = chat(get_input_dir(req.project), req.project, req.text, req.session_id)
        session_id = outcome.get("session_id", session_id)
        ensure_session(session_id, req.project)
        update_task_status(task_id, "done")
        return CommandResponse(session_id=session_id, task_id=task_id,
            intent_display="OpenAI chat agent", workflow_display="Conversation",
            parsed={"intent": "CHAT", "raw_text": req.text, "parameters": {}},
            result=outcome)
    except ValueError as exc:
        update_task_status(task_id, "failed", error_msg=str(exc))
        return CommandResponse(session_id=session_id, task_id=task_id,
            intent_display="OpenAI chat agent", workflow_display="Stopped safely",
            parsed={}, error=str(exc))



@app.post("/api/execute/comparison", response_model=CommandResponse)
async def execute_comparison(req: ExecuteComparisonRequest) -> CommandResponse:
    """Thực thi comparison sau khi người dùng cung cấp primary key."""
    input_dir = get_input_dir(req.project)
    try:
        # Explicit API arguments are filenames, never arbitrary filesystem paths.
        root = input_dir.resolve()
        listed = {p.name for p in list_excel_files(input_dir)}
        for name in (req.root_file, req.update_file):
            if name is not None and (name not in listed or
                    not (input_dir / name).resolve().is_relative_to(root)):
                raise ValueError("Comparison source must be an exact filename inside project input.")
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
        from app.services.sources.file_manager import _safe_resolve
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
        "system": "Excel Assistant API (OpenAI)",
        "status": "running",
        "chatbot_ui": "http://localhost:8501",
        "docs": "http://localhost:8000/docs"
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Excel Rule Engine"}


@app.get("/api/planner/status")
def report_planner_status():
    """Expose mode, never credentials."""
    from app.services.ai.planner_settings import planner_status
    try:
        return planner_status()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class ChatTurnRequest(BaseModel):
    text: str
    project: str = "demo_project"
    session_id: str | None = None


class ChatUpdateConfirm(BaseModel):
    project: str = "demo_project"
    session_id: str
    token: str


@app.post("/api/chat/sources/upload")
async def upload_chat_source(project: str = Form("demo_project"), file: UploadFile = File(...)):
    from app.services.sources.source_uploads import save_source
    try:
        raw = await file.read(40 * 1024 * 1024 + 1)
        return save_source(get_input_dir(project), file.filename, raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()


@app.post("/api/chat")
def conversation_turn(req: ChatTurnRequest):
    from app.services.chat.chat_conversation import chat
    try:
        return chat(get_input_dir(req.project), req.project, req.text, req.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat/update/cancel")
def conversation_update_cancel(req: ChatUpdateConfirm):
    from app.services.chat.chat_conversation import cancel
    try:
        return cancel(get_input_dir(req.project), req.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat/update/confirm")
def conversation_update_confirm(req: ChatUpdateConfirm):
    from app.services.chat.chat_conversation import confirm
    try:
        return confirm(get_input_dir(req.project), req.session_id, req.token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class ReportPlanRequest(BaseModel):
    text: str
    project: str = "demo_project"
    source_name: str | None = None


class ConfirmReportRequest(ReportPlanRequest):
    fingerprint: str


@app.post("/api/report/preview")
async def preview_conversation_report(req: ReportPlanRequest):
    """Inspect an explicit source selection; never generate an output here."""
    from app.services.reports.conversation_reporting import preview_request
    try:
        return preview_request(get_input_dir(req.project), req.text, req.source_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/report/auto")
async def automatic_conversation_report(req: ReportPlanRequest):
    """Execute a ready plan on one snapshot, otherwise ask for missing input."""
    from app.services.reports.conversation_reporting import automatic_request
    try:
        return automatic_request(get_input_dir(req.project), req.project, req.text, req.source_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/report/confirm")
async def confirm_conversation_report(req: ConfirmReportRequest):
    """Rebuild and validate the approved plan against current source bytes."""
    from app.services.reports.conversation_reporting import execute_request
    try:
        return {"result": execute_request(get_input_dir(req.project), req.project, req.text,
                                          req.source_name, req.fingerprint)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if __name__ == "__main__":
    import subprocess
    import sys
    import time
    import uvicorn

    print("\n" + "=" * 55)
    print("   KHỞI ĐỘNG EXCEL RULE ENGINE SYSTEM")
    print("=" * 55)

    chatbot_script = Path(__file__).resolve().parent / "ui" / "chatbot.py"
    
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
