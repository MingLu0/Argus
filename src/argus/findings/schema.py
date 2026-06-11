from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class FindingAction(StrEnum):
    NO_OP = "no-op"
    RECOMMEND = "recommend"
    ASK_USER = "ask-user"
    BLOCK = "block"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Recommendation(StrEnum):
    APPROVE = "approve"
    REVISE = "revise"
    REJECT = "reject"
    UNCERTAIN = "uncertain"


class Finding(BaseModel):
    id: str = ""
    severity: Severity
    action: FindingAction
    claim: str
    evidence: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    affected_decision: str = "general"


class ReviewResult(BaseModel):
    reviewer_id: str
    recommendation: Recommendation = Recommendation.UNCERTAIN
    risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_rationale: str = ""
    findings: list[Finding] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    parse_error: str | None = None
