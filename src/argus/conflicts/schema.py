from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from argus.findings.schema import Confidence, FindingAction, RiskLevel, Severity


class ConflictStatus(StrEnum):
    UNRESOLVED = "unresolved"
    NON_CONFLICTING = "non_conflicting"


class ConflictPosition(BaseModel):
    reviewer_id: str
    finding_id: str
    claim: str
    action: FindingAction
    severity: Severity
    confidence: Confidence
    evidence: list[str] = Field(default_factory=list)


class Conflict(BaseModel):
    id: str
    affected_decision: str
    risk_level: RiskLevel
    status: ConflictStatus
    rationale: str
    positions: list[ConflictPosition] = Field(default_factory=list)


class DecisionGate(BaseModel):
    required: bool
    reasons: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    conflict_ids: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    successful_reviewers: int
    minimum_successful_reviewers: int
