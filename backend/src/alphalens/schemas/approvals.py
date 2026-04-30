"""Compatibility exports for approval workflow schemas."""

from alphalens.schemas.approval import (
    ApprovalActionType,
    ApprovalDecision,
    ApprovalRecord,
    ApprovalStatus,
)

Approval = ApprovalRecord
ApprovalKind = ApprovalActionType
