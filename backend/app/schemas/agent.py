from typing import Literal

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    #: Which model should answer: "ollama", "gemini", or None for the
    #: configured default. The Chat page's switcher sets this.
    provider: str | None = Field(default=None, max_length=20)
    #: Which saved thread this belongs to. Omit to start a new one; the reply
    #: carries the id to use for the rest of the conversation.
    conversation_id: str | None = Field(default=None, max_length=40)
    #: How hard the model should think: "low", "medium" or "high". Omit for
    #: the model's default. Higher is slower but more careful.
    effort: Literal["low", "medium", "high"] | None = None
    #: Reply language chosen in the menu, e.g. "Hindi". Omit to answer in the
    #: language the student writes in.
    language: str | None = Field(default=None, max_length=30, pattern=r"^[A-Za-z][A-Za-z ()-]*$")
    #: True when asked in voice mode: the answer is read aloud, so it should be
    #: short and plain (no tables, charts or extra detail).
    voice: bool = False


class AgentChatResponse(BaseModel):
    answer: str
    intent: str
    tool_used: str | None
    source: str
    action: str | None = None
    #: Which model actually answered - not necessarily the one asked for.
    provider: str = ""
    provider_label: str = ""
    model: str = ""
    #: Providers that were tried first and failed, with the reason. Empty when
    #: the requested model answered.
    fell_back_from: list[dict[str, str]] = []
    note: str = ""
    #: The thread this answer was saved to, and its title.
    conversation_id: str = ""
    conversation_title: str = ""
    #: How many earlier turns were sent with the question.
    history_turns: int = 0


class AgentProvider(BaseModel):
    id: str
    label: str
    model: str
    available: bool
    reason: str = ""


class AgentProviders(BaseModel):
    default: str
    providers: list[AgentProvider]


class ConversationSummary(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str
    has_summary: bool = False


class ConversationMessageOut(BaseModel):
    id: int
    role: str
    content: str
    tool_used: str = ""
    source: str = ""
    provider: str = ""
    model: str = ""
    created_at: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str
    summary: str = ""
    messages: list[ConversationMessageOut] = []


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=120)
