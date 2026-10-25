"""HTTP API for the chatbot: chat, saved conversations, and the UMS session."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.providers import ask as ask_agent, describe as describe_providers
from app.core.config import settings
from app.db.session import get_db
from app.repositories.conversation import (
    delete_conversation,
    get_conversation,
    list_conversations,
    list_messages,
    rename_conversation,
)
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentProviders,
    ConversationDetail,
    ConversationMessageOut,
    ConversationRename,
    ConversationSummary,
)
from app.ums.playwright_service import ums_playwright
from app.ums.state import UMSLiveAttendanceUnavailable

router = APIRouter(prefix="/api")

#: Single-user app: every conversation belongs to this id.
STUDENT_ID = "student"


# ------------------------------------------------------------------ chat
@router.get("/agent/providers", response_model=AgentProviders)
def agent_providers():
    """Which models can answer, and which one answers by default."""
    return AgentProviders(**describe_providers())


@router.post("/agent/chat", response_model=AgentChatResponse)
def agent_chat(payload: AgentChatRequest, db: Session = Depends(get_db)):
    """Answer with the requested model, or the configured default."""
    try:
        return AgentChatResponse(**ask_agent(
            payload.message, STUDENT_ID, db, payload.provider, payload.conversation_id,
            effort=payload.effort,
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


def _find(db: Session, conversation_id: str):
    found = get_conversation(db, conversation_id, STUDENT_ID)
    if found is None:
        raise HTTPException(status_code=404, detail="That conversation does not exist.")
    return found


@router.get("/conversations", response_model=list[ConversationSummary])
def conversations(db: Session = Depends(get_db)):
    """Saved chat threads, most recently used first."""
    return [_thread(item) for item in list_conversations(db, STUDENT_ID, settings.chat_max_conversations)]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation_detail(conversation_id: str, db: Session = Depends(get_db)):
    """One thread with every message, to restore the chat on screen."""
    found = _find(db, conversation_id)
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
def rename_conversation_route(conversation_id: str, payload: ConversationRename, db: Session = Depends(get_db)):
    return _thread(rename_conversation(db, _find(db, conversation_id), payload.title))


@router.delete("/conversations/{conversation_id}")
def delete_conversation_route(conversation_id: str, db: Session = Depends(get_db)):
    delete_conversation(db, _find(db, conversation_id))
    return {"deleted": conversation_id}


# ------------------------------------------------------------------ UMS session
@router.post("/ums/session/start")
def ums_session_start():
    """Open the dedicated browser at UMS; the student signs in there by hand."""
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
        diagnostics = exc.diagnostics or {}
        raise HTTPException(status_code=409, detail={
            "message": str(exc), "state": diagnostics.get("state"), "diagnostics": diagnostics,
        }) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc


@router.post("/ums/session/stop")
def ums_session_stop():
    try:
        return ums_playwright.stop()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ums/diagnostics")
def ums_diagnostics():
    """How far the UMS pipeline got, for debugging without reading logs."""
    return ums_playwright.diagnostics()
