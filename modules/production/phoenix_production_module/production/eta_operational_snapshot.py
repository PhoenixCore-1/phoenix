from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .eta_required_risk import RequiredDateRiskLevel
from .eta_risk import ETARiskLevel
from .eta_risk_summary import (
    ETARiskDecision,
    ETARiskSummary,
)


@dataclass(frozen=True)
class ETAOperationalSnapshot:
    """
    Read-only operational ETA view for Phoenix Production.

    This object is intentionally presentation-neutral.

    It combines the information required by the Phoenix Core
    production/status layer without making the Core dependent
    on the underlying ETA calculation implementations.
    """

    planned_eta: Optional[datetime]
    current_eta: Optional[datetime]
    required_date: Optional[datetime]

    schedule_risk: ETARiskLevel
    required_date_risk: RequiredDateRiskLevel
    decision: ETARiskDecision

    action_required: bool
    summary: str

    @classmethod
    def from_risk_summary(
        cls,
        *,
        planned_eta: Optional[datetime],
        current_eta: Optional[datetime],
        required_date: Optional[datetime],
        summary: ETARiskSummary,
    ) -> "ETAOperationalSnapshot":
        """
        Build an operational snapshot from the existing
        ETA risk summary.

        No risk calculation is performed here.

        The snapshot is a read-only projection of already
        calculated production information.
        """

        return cls(
            planned_eta=planned_eta,
            current_eta=current_eta,
            required_date=required_date,
            schedule_risk=summary.schedule_risk,
            required_date_risk=summary.required_date_risk,
            decision=summary.decision,
            action_required=summary.action_required,
            summary=summary.summary,
        )

    @property
    def is_on_track(self) -> bool:
        """
        True when the operational decision is ON_TRACK.
        """

        return (
            self.decision
            == ETARiskDecision.ON_TRACK
        )

    @property
    def is_customer_safe(self) -> bool:
        """
        True when the required date is currently considered
        safe.
        """

        return self.required_date_risk in (
            RequiredDateRiskLevel.ON_TIME,
            RequiredDateRiskLevel.AT_RISK,
        )

    @property
    def is_customer_at_risk(self) -> bool:
        """
        True when the required date is inside the defined
        customer-date risk condition.
        """

        return (
            self.required_date_risk
            == RequiredDateRiskLevel.AT_RISK
        )

    @property
    def is_customer_late(self) -> bool:
        """
        True when the required date is expected to be missed.
        """

        return (
            self.required_date_risk
            == RequiredDateRiskLevel.LATE
        )

    @property
    def requires_action(self) -> bool:
        """
        Convenience alias for action_required.
        """

        return self.action_required