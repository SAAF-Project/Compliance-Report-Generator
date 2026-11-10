from __future__ import annotations

import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, Field
from pydantic_core import PydanticCustomError

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

Industry = Literal[
    "Financial Services",
    "Healthcare",
    "Technology",
    "Energy",
    "Retail",
    "Manufacturing",
    "Government",
    "Telecommunications",
    "Real Estate",
    "Education",
]

ListedStatus = Literal["Public", "Private", "Government"]

AuditTopic = Literal[
    "Cybersecurity",
    "Data Privacy",
    "Financial Reporting",
    "Vendor Management",
    "Business Continuity",
    "IT General Controls",
    "Anti-Money Laundering",
    "ESG & Sustainability",
    "Operational Risk",
]


# Cc is the C0/C1 control characters (newline, tab, NEL, ...); Zl and Zp are the
# Unicode line and paragraph separators. Cf is invisible formatting, including tag
# characters that can carry hidden text to the model and bidi overrides. Deliberately
# not an ASCII allowlist, and the zero-width (non-)joiner stay allowed: names in
# non-Latin scripts can need them.
_REJECTED_CATEGORIES = {"Cc", "Cf", "Zl", "Zp"}
_ALLOWED_FORMAT_CHARACTERS = {"\u200c", "\u200d"}


def _reject_control_characters(value: str) -> str:
    if any(
        unicodedata.category(char) in _REJECTED_CATEGORIES
        and char not in _ALLOWED_FORMAT_CHARACTERS
        for char in value
    ):
        raise PydanticCustomError(
            "control_characters",
            "must not contain control characters or invisible formatting characters, "
            "such as newlines or tabs",
        )
    return value


CompanyName = Annotated[str, Field(max_length=200), AfterValidator(_reject_control_characters)]
Country = Annotated[str, Field(max_length=100), AfterValidator(_reject_control_characters)]


class AuditInput(BaseModel):
    company_name: CompanyName
    industry: Industry
    country: Country
    listed_status: ListedStatus
    audit_topic: AuditTopic


# ---------------------------------------------------------------------------
# Output building blocks
# ---------------------------------------------------------------------------

Priority = Literal["Critical", "High", "Medium", "Low"]
RiskRating = Literal["Critical", "High", "Medium", "Low"]
RemediationEffort = Literal["Low", "Medium", "High", "Very High"]


class ControlObjective(BaseModel):
    control_id: str = Field(description="Short unique ID, e.g. ISO-AC-01")
    description: str = Field(description="What the control requires")
    requirement_source: str = Field(description="Clause / section reference, e.g. ISO 27001 A.8.3")
    testing_approach: str = Field(description="How an auditor would test this control")
    priority: Priority


class FrameworkAssessment(BaseModel):
    framework_name: str
    applicability_rationale: str = Field(
        description="Why this framework applies to the given inputs"
    )
    control_objectives: list[ControlObjective]
    key_gaps: list[str] = Field(description="Typical gaps for this profile")
    risk_rating: RiskRating


class RegulatoryRequirement(BaseModel):
    regulation_name: str
    jurisdiction: str
    mandatory: bool
    applicable_sections: list[str]
    compliance_notes: str = Field(
        description="Key compliance obligations or deadlines"
    )


class GapRiskSummary(BaseModel):
    overall_risk_rating: RiskRating
    critical_gaps: list[str]
    recommended_priority_actions: list[str]
    estimated_remediation_effort: RemediationEffort
    executive_summary: str = Field(
        description="2-3 sentence plain-English summary for non-technical stakeholders"
    )


ReferenceCheckKind = Literal[
    "identifier_found",         # identifier exists in the official clause list
    "parent_identifier_found",  # reference is finer than the list; its parent exists
    "identifier_not_found",     # framework covered, identifier not in its official list
    "no_locator",               # framework recognised, no clause locator in the text
    "framework_not_covered",    # mapped framework without an official clause list yet
    "unmapped_framework",       # names no framework in the mapped set
]


class ReferenceCheck(BaseModel):
    """Result of checking one model-generated clause reference.

    Set by the agent after validation; never requested from the model.
    ``status`` is always "unverified": even a found identifier only proves the
    clause exists, not that it says what the model claims.
    """

    location: str = Field(description="Control ID or '<regulation> (regulation)'")
    field: Literal["requirement_source", "applicable_sections"]
    reference: str
    framework_key: Optional[str] = None
    status: Literal["unverified"] = "unverified"
    check: ReferenceCheckKind
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Heuristic score from the check outcome, not a probability. "
                    "Never 1.0 because clause content is not verified.",
    )
    matched_identifiers: list[str] = Field(default_factory=list)
    note: str = ""


# ---------------------------------------------------------------------------
# Top-level report
# ---------------------------------------------------------------------------

DISCLAIMER = (
    "This report is generated by an AI system and is intended as a "
    "starting point for internal audit planning. It does not constitute "
    "legal or professional compliance advice. Always engage qualified "
    "compliance professionals to confirm regulatory obligations."
)


class ComplianceReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    audit_input: AuditInput
    mandatory_regulations: list[RegulatoryRequirement]
    framework_assessments: list[FrameworkAssessment]
    gap_risk_summary: GapRiskSummary
    disclaimer: str = DISCLAIMER
    # Set by the agent after validation; never requested from the model.
    warnings: list[str] = Field(default_factory=list)
    # Set by the agent after validation; never requested from the model.
    reference_checks: list[ReferenceCheck] = Field(default_factory=list)
