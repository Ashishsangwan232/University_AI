from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.providers import ask as ask_agent, describe as describe_providers
from app.core.config import settings
from app.db.session import get_db
from app.rag.service import ingest_website, search_knowledge
from app.repositories.campus import search_services
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentProviders,
    ConversationDetail,
    ConversationMessageOut,
    ConversationRename,
    ConversationSummary,
)
from app.schemas.attendance import (
    AttendanceCalculateRequest,
    AttendanceCalculateResponse,
    AttendanceResponse,
)
from app.schemas.campus import CollegeServiceResponse
from app.schemas.rag import RAGIngestRequest, RAGIngestResponse, RAGSearchRequest
from app.schemas.student import StudentProfile
from app.services.attendance import calculate
from app.tools.attendance import get_attendance as attendance_tool
from app.ums.playwright_service import ums_playwright
from app.ums.state import UMSLiveAttendanceUnavailable

router = APIRouter(prefix="/api")


def _unavailable(exc: UMSLiveAttendanceUnavailable) -> HTTPException:
    """409 carrying the state machine position, so the failure point is visible."""
    diagnostics = exc.diagnostics or {}
    return HTTPException(
        status_code=409,
        detail={
            "message": str(exc),
            "state": diagnostics.get("state"),
            "diagnostics": diagnostics,
        },
    )


@router.get("/student", response_model=StudentProfile)
def student_profile(db: Session = Depends(get_db)):
    """The student's real identity from UMS, demo record only when offline.

    Never returns the demo student while UMS is authenticated - a wrong name is
    as misleading as a wrong attendance percentage.
    """
    from app.tools.student import get_student_profile

    try:
        return StudentProfile(**get_student_profile("student-demo", db))
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/ums/profile")
def ums_profile(force: bool = False):
    """Raw identity reading from UMS, with the attempts that produced it."""
    try:
        return ums_playwright.student_profile(force=force)
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/attendance", response_model=AttendanceResponse)
def get_attendance(db: Session = Depends(get_db)):
    """Live UMS attendance whenever the UMS session is authenticated.

    When UMS is authenticated but extraction fails, this returns 409 with the
    exact state machine position. It never silently substitutes demo data for a
    connected session.
    """
    try:
        return AttendanceResponse(**attendance_tool("student-demo", db))
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.post("/attendance/calculate", response_model=AttendanceCalculateResponse)
def calculate_attendance(payload: AttendanceCalculateRequest):
    # Deterministic backend arithmetic; the model never does this itself.
    return calculate(payload.attended, payload.total, payload.target_percentage)


@router.get("/timetable")
def timetable(db: Session = Depends(get_db)):
    """Live UMS timetable when connected, clearly labelled demo rows otherwise."""
    from app.tools.campus import get_timetable_tool

    try:
        return get_timetable_tool("student-demo", db)
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.post("/leave/draft")
def leave_draft(payload: dict[str, Any] | None = None):
    """Validate a hostel leave draft. Touches nothing in UMS.

    Dates, durations and balance arithmetic are checked here, in Python, not by
    the language model.
    """
    from app.tools.campus import draft_leave_tool

    try:
        return draft_leave_tool(payload or {})
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.post("/ums/leave/prefill")
def ums_leave_prefill(payload: dict[str, Any] | None = None):
    """Type a validated draft into the UMS leave form and stop there.

    Deliberately NOT a Gemini tool: the model drafts, a person presses the
    button. Off unless UMS_ALLOW_PREFILL=true. Even then it fills five fields,
    never ticks the acknowledgement, and never clicks Submit.
    """
    from app.tools.campus import draft_leave_tool

    payload = payload or {}
    checked = draft_leave_tool(payload)
    if not checked["ok"]:
        raise HTTPException(status_code=422, detail={
            "message": "The draft is not valid, so nothing was typed into UMS.",
            "errors": checked["errors"],
        })
    try:
        return {**ums_playwright.prefill_leave(checked["draft"]), "review": checked}
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/ums/leave")
def ums_leave(force: bool = False):
    """Hostel leave balances and authorities, read from UMS.

    READ ONLY: this opens the leave page with a GET and reads it. CampusAI never
    fills the form, never ticks the acknowledgement, and never clicks Submit -
    there is no endpoint that does, by design.
    """
    try:
        return ums_playwright.leave(force=force)
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/ums/timetable")
def ums_timetable(force: bool = False):
    """Live timetable straight from the UMS session. No demo fallback."""
    try:
        return ums_playwright.timetable(force=force)
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/announcements")
def announcements(db: Session = Depends(get_db)):
    """Live UMS announcements when connected, clearly labelled demo rows otherwise.

    Same rule as attendance: an authenticated session never silently falls back
    to PostgreSQL.
    """
    from app.tools.campus import get_announcements_tool

    try:
        return get_announcements_tool(db)
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/messages")
def messages():
    """Live UMS messages. There is no demo equivalent, so this needs UMS."""
    from app.tools.campus import get_messages_tool

    try:
        return get_messages_tool()
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/services", response_model=list[CollegeServiceResponse])
def services(db: Session = Depends(get_db)):
    return search_services(db)


@router.get("/agent/providers", response_model=AgentProviders)
def agent_providers():
    """Which models can answer, and which one answers by default."""
    return AgentProviders(**describe_providers())


@router.post("/agent/chat", response_model=AgentChatResponse)
def agent_chat(payload: AgentChatRequest, db: Session = Depends(get_db)):
    """Answer with the requested model, or the configured default.

    Provider selection, the backup model and the no-model fallback all live in
    app.agent.providers, and the response says which model actually replied.
    """
    try:
        return AgentChatResponse(**ask_agent(
            payload.message, "student-demo", db, payload.provider, payload.conversation_id
        ))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"No AI backend could answer: {exc}") from exc


# --------------------------------------------------------------- conversations
def _thread(conversation) -> ConversationSummary:
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        message_count=conversation.message_count,
        created_at=conversation.created_at.isoformat() if conversation.created_at else "",
        updated_at=conversation.updated_at.isoformat() if conversation.updated_at else "",
        has_summary=bool(conversation.summary),
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def conversations(db: Session = Depends(get_db)):
    """Saved chat threads, most recently used first."""
    from app.repositories.conversation import list_conversations

    return [_thread(item) for item in list_conversations(db, "student-demo", settings.chat_max_conversations)]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation_detail(conversation_id: str, db: Session = Depends(get_db)):
    """One thread with every message, to restore the chat on screen."""
    from app.repositories.conversation import get_conversation, list_messages

    found = get_conversation(db, conversation_id, "student-demo")
    if found is None:
        raise HTTPException(status_code=404, detail="That conversation does not exist.")
    return ConversationDetail(
        **_thread(found).model_dump(exclude={"has_summary"}),
        summary=found.summary,
        messages=[
            ConversationMessageOut(
                id=message.id,
                role=message.role,
                content=message.content,
                tool_used=message.tool_used,
                source=message.source,
                provider=message.provider,
                model=message.model,
                created_at=message.created_at.isoformat() if message.created_at else "",
            )
            for message in list_messages(db, conversation_id)
        ],
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
def rename_conversation_route(
    conversation_id: str, payload: ConversationRename, db: Session = Depends(get_db)
):
    from app.repositories.conversation import get_conversation, rename_conversation

    found = get_conversation(db, conversation_id, "student-demo")
    if found is None:
        raise HTTPException(status_code=404, detail="That conversation does not exist.")
    return _thread(rename_conversation(db, found, payload.title))


@router.delete("/conversations/{conversation_id}")
def delete_conversation_route(conversation_id: str, db: Session = Depends(get_db)):
    from app.repositories.conversation import delete_conversation, get_conversation

    found = get_conversation(db, conversation_id, "student-demo")
    if found is None:
        raise HTTPException(status_code=404, detail="That conversation does not exist.")
    delete_conversation(db, found)
    return {"deleted": conversation_id}


@router.post("/rag/ingest", response_model=RAGIngestResponse)
def rag_ingest(payload: RAGIngestRequest):
    """Crawl the public college website into the local knowledge base.

    Long-running: a 150-page crawl takes several minutes. Prefer
    `python scripts/ingest_site.py`, which prints progress as it goes.
    """
    try:
        return ingest_website(payload.url, payload.max_pages, payload.max_depth)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/rag/search")
def rag_search(payload: RAGSearchRequest):
    try:
        return search_knowledge(payload.query, payload.limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/rag/status")
def rag_status():
    """What has been ingested, and whether semantic search is working."""
    from app.rag.service import knowledge_status

    return knowledge_status()


@router.delete("/rag/knowledge")
def rag_clear():
    """Empty the knowledge base. Only removes CampusAI's own crawl."""
    from app.rag.service import clear_knowledge

    return clear_knowledge()


# ------------------------------------------------------------------ UMS session


@router.post("/ums/session/start")
def ums_session_start():
    try:
        return ums_playwright.start()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ums/session/status")
def ums_session_status():
    return ums_playwright.status()


@router.post("/ums/session/refresh")
def ums_session_refresh():
    try:
        return ums_playwright.refresh()
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc


@router.post("/ums/session/navigate")
def ums_session_navigate(payload: dict[str, str]):
    try:
        return ums_playwright.navigate(payload.get("target", "dashboard"))
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc


@router.post("/ums/session/stop")
def ums_session_stop():
    try:
        return ums_playwright.stop()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ums/attendance/status")
def ums_attendance_status():
    return ums_playwright.status()


@router.get("/ums/explore")
def ums_explore():
    """List every attendance-looking control on the current UMS page, ranked.

    Read-only: it clicks nothing. Use it to see why the wrong control was picked,
    or why none was found.
    """
    try:
        return ums_playwright.explore()
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc


@router.get("/ums/attendance/detail")
def ums_attendance_detail(force: bool = False):
    """Class-by-class attendance per course, from the authenticated UMS session."""
    try:
        return ums_playwright.attendance_detail(force=force)
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/ums/announcements")
def ums_announcements(force: bool = False):
    """Live announcements from the authenticated UMS session. No demo fallback."""
    try:
        return ums_playwright.announcements(force=force)
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/ums/messages")
def ums_messages(force: bool = False):
    """Live messages from the authenticated UMS session. No demo fallback."""
    try:
        return ums_playwright.messages(force=force)
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.post("/ums/inspect")
def ums_inspect(payload: dict[str, Any] | None = None):
    """Structural probe of specific containers, for designing a parser.

    Reads the DOM and optionally clicks the named openers to render a hidden
    panel. Navigates nothing and submits nothing.
    """
    payload = payload or {}
    selectors = payload.get("selectors") or ["#tAC", "#MyMessage"]
    try:
        return ums_playwright.inspect(
            list(selectors)[:12],
            int(payload.get("depth") or 3),
            bool(payload.get("html")),
            list(payload.get("openers") or []),
            str(payload.get("url") or ""),
            float(payload.get("wait") or 2.0),
        )
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/ums/map")
def ums_map():
    """Read-only inventory of the current UMS page: links, click handlers,
    panels, tables, and inline script names, grouped by feature.

    Navigates nothing and clicks nothing.
    """
    try:
        return ums_playwright.site_map()
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.post("/ums/map/crawl")
def ums_map_crawl(payload: dict[str, Any] | None = None):
    """Inventory the dashboard, then open a few safe report pages by URL.

    Only same-host .aspx links that are not flagged as actions (apply, submit,
    pay, delete, ...) are opened, each by direct navigation. Nothing is clicked
    and no form is submitted. The browser is returned to where it started.
    """
    payload = payload or {}
    topics = payload.get("topics") or ["messages", "announcements"]
    max_visits = int(payload.get("max_visits") or 6)
    try:
        return ums_playwright.crawl(list(topics), min(max_visits, 15))
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/ums/diagnostics")
def ums_diagnostics_endpoint():
    """Exactly how far the pipeline got, for debugging without reading logs."""
    return ums_playwright.diagnostics()


@router.get("/ums/attendance")
def ums_attendance():
    try:
        return ums_playwright.attendance()
    except UMSLiveAttendanceUnavailable as exc:
        raise _unavailable(exc) from exc
