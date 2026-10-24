"""Shared-state schema. Every agent reads from and writes to RunState; nothing else is shared."""
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    source: Literal["profile", "products", "inventory", "engagement"]
    detail: str                       # concrete fact, e.g. "Jute Tote Bag restocked 2026-10-18, 24 units"


class Recommendation(BaseModel):
    type: Literal["caption", "promo_post", "stock_update"]
    draft: str
    suggested_time: Optional[str] = None
    rationale: str
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    warnings: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    task_type: Literal["caption", "promo_post", "stock_update"] = "promo_post"
    num_recommendations: int = Field(default=2, ge=1, le=3)
    data_needed: list[Literal["profile", "products", "inventory", "engagement"]]
    success_criteria: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class Review(BaseModel):
    verdict: Literal["pass", "revise", "escalate"]
    issues: list[str] = Field(default_factory=list)
    feedback: str = ""


class ReporterOut(BaseModel):
    summary: str
    priority_order: list[int] = Field(default_factory=list)   # indexes into drafts, best first
    questions_for_owner: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Message(BaseModel):
    ts: str
    agent: str
    kind: str                         # plan | tool_call | tool_result | draft | review | fallback | final ...
    content: Any


class FinalOutput(BaseModel):
    """This is the JSON the backend returns to the frontend."""
    run_id: str
    status: Literal["approved", "approved_with_caveats", "needs_input", "error"]
    summary: str
    recommendations: list[Recommendation]
    data_gaps: list[str]
    questions_for_owner: list[str]
    limitations: list[str]
    revisions_used: int


class RunState(BaseModel):
    run_id: str
    business_id: str
    request: str
    sample_mode: bool = False
    started_at: float
    selection_notes: list[str] = Field(default_factory=list)
    memory_context: str = ""
    memory_trace: dict[str, Any] = Field(default_factory=dict)
    plan: Optional[Plan] = None
    tool_data: dict[str, Any] = Field(default_factory=dict)     # kind -> raw data from the backend
    drafts: list[Recommendation] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)            # fallbacks that happened during the run
    reviews: list[Review] = Field(default_factory=list)
    revision_count: int = 0
    log: list[Message] = Field(default_factory=list)
    final: Optional[dict] = None
