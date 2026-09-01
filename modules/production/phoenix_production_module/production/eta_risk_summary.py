from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .eta_required_risk import (
    RequiredDateRisk,
    RequiredDateRiskLevel,
)
from .eta_risk import (
    ETARiskLevel,
    ETAScheduleVariance,
)


# ---------------------------------------------------------------------------
# Phoenix Production Module 1.3.20
# ETA Risk Summary / Decision Layer
# ---------------------------------------------------------------------------


class ETARiskDecision(str, Enum):
    """
    Operational interpretation of the two independent ETA risk views.

    Schedule risk answers:

        "Are we behind the internal production plan?"

    Required-date risk answers:

        "Can we meet the required/customer date?"

    This decision layer combines those two answers into a single
    operational interpretation.

    The underlying risk calculations remain independent.
    """

    UNKNOWN = "UNKNOWN"

    ON_TRACK = "ON_TRACK"

    BEHIND_PLAN_CUSTOMER_SAFE = (
        "BEHIND_PLAN_CUSTOMER_SAFE"
    )

    SCHEDULE_AT_RISK_CUSTOMER_SAFE = (
        "SCHEDULE_AT_RISK_CUSTOMER_SAFE"
    )

    CUSTOMER_DATE_AT_RISK = (
        "CUSTOMER_DATE_AT_RISK"
    )

    CUSTOMER_DATE_LATE = (
        "CUSTOMER_DATE_LATE"
    )

    REQUIRED_DATE_CONFLICT = (
        "REQUIRED_DATE_CONFLICT"
    )

    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class ETARiskSummary:
    """
    Combined operational interpretation of:

        1. Internal schedule risk
        2. Required/customer-date risk

    The summary is immutable and read-only.

    It does not modify the ManufacturingOrder or either underlying
    risk result.
    """

    schedule_risk: ETARiskLevel
    required_date_risk: RequiredDateRiskLevel
    decision: ETARiskDecision
    summary: str
    action_required: bool
    customer_date_safe: bool
    schedule_is_safe: bool

    @property
    def is_on_track(self) -> bool:
        return (
            self.decision
            == ETARiskDecision.ON_TRACK
        )

    @property
    def is_customer_safe(self) -> bool:
        return self.customer_date_safe

    @property
    def is_customer_at_risk(self) -> bool:
        return (
            self.required_date_risk
            == RequiredDateRiskLevel.AT_RISK
        )

    @property
    def is_customer_late(self) -> bool:
        return (
            self.required_date_risk
            == RequiredDateRiskLevel.LATE
        )

    @property
    def requires_action(self) -> bool:
        return self.action_required


class ETARiskSummaryCalculator:
    """
    Combines internal schedule risk and required-date risk into
    one operational decision.

    No database access occurs here.

    No ManufacturingOrder is modified.

    No Upat-specific rules are embedded.
    """

    # ============================================================
    # PUBLIC CALCULATION
    # ============================================================

    def calculate(
        self,
        *,
        schedule_risk: ETAScheduleVariance,
        required_date_risk: RequiredDateRisk,
    ) -> ETARiskSummary:
        """
        Produce one operational ETA decision from the two
        independent risk calculations.
        """

        schedule_level = (
            schedule_risk.risk_level
        )

        required_level = (
            required_date_risk.risk_level
        )

        decision = self._determine_decision(
            schedule_level=schedule_level,
            required_level=required_level,
        )

        summary = self._build_summary(
            decision=decision,
            schedule_level=schedule_level,
            required_level=required_level,
        )

        customer_date_safe = (
            required_level
            in (
                RequiredDateRiskLevel.ON_TIME,
                RequiredDateRiskLevel.AT_RISK,
                RequiredDateRiskLevel.COMPLETED,
            )
        )

        schedule_is_safe = (
            schedule_level
            == ETARiskLevel.ON_TRACK
        )

        action_required = (
            decision
            in (
                ETARiskDecision.SCHEDULE_AT_RISK_CUSTOMER_SAFE,
                ETARiskDecision.BEHIND_PLAN_CUSTOMER_SAFE,
                ETARiskDecision.CUSTOMER_DATE_AT_RISK,
                ETARiskDecision.CUSTOMER_DATE_LATE,
                ETARiskDecision.REQUIRED_DATE_CONFLICT,
            )
        )

        return ETARiskSummary(
            schedule_risk=schedule_level,
            required_date_risk=required_level,
            decision=decision,
            summary=summary,
            action_required=action_required,
            customer_date_safe=customer_date_safe,
            schedule_is_safe=schedule_is_safe,
        )

    # ============================================================
    # DECISION MATRIX
    # ============================================================

    def _determine_decision(
        self,
        *,
        schedule_level: ETARiskLevel,
        required_level: RequiredDateRiskLevel,
    ) -> ETARiskDecision:
        """
        Apply the operational decision matrix.

        Priority:

            1. Completed
            2. Missing/unknown information
            3. Customer-date late
            4. Customer-date at risk
            5. Internal schedule issue
            6. Fully on track
        """

        if (
            required_level
            == RequiredDateRiskLevel.COMPLETED
        ):
            return ETARiskDecision.COMPLETED

        if (
            schedule_level
            == ETARiskLevel.UNKNOWN
            or required_level
            == RequiredDateRiskLevel.UNKNOWN
        ):
            return ETARiskDecision.UNKNOWN

        if (
            required_level
            == RequiredDateRiskLevel.LATE
        ):
            if (
                schedule_level
                == ETARiskLevel.ON_TRACK
            ):
                return (
                    ETARiskDecision.REQUIRED_DATE_CONFLICT
                )

            return (
                ETARiskDecision.CUSTOMER_DATE_LATE
            )

        if (
            required_level
            == RequiredDateRiskLevel.AT_RISK
        ):
            return (
                ETARiskDecision.CUSTOMER_DATE_AT_RISK
            )

        # Required date is ON_TIME.

        if (
            schedule_level
            == ETARiskLevel.LATE
        ):
            return (
                ETARiskDecision.BEHIND_PLAN_CUSTOMER_SAFE
            )

        if (
            schedule_level
            == ETARiskLevel.AT_RISK
        ):
            return (
                ETARiskDecision.SCHEDULE_AT_RISK_CUSTOMER_SAFE
            )

        return ETARiskDecision.ON_TRACK

    # ============================================================
    # SUMMARY TEXT
    # ============================================================

    @staticmethod
    def _build_summary(
        *,
        decision: ETARiskDecision,
        schedule_level: ETARiskLevel,
        required_level: RequiredDateRiskLevel,
    ) -> str:
        if decision == ETARiskDecision.COMPLETED:
            return (
                "Production is completed"
            )

        if decision == ETARiskDecision.UNKNOWN:
            return (
                "ETA risk cannot be determined because "
                "required risk information is incomplete"
            )

        if (
            decision
            == ETARiskDecision.ON_TRACK
        ):
            return (
                "Production is on track and the required "
                "date is safe"
            )

        if (
            decision
            == ETARiskDecision.BEHIND_PLAN_CUSTOMER_SAFE
        ):
            return (
                "Production is behind plan but the "
                "required date remains safe"
            )

        if (
            decision
            == ETARiskDecision.SCHEDULE_AT_RISK_CUSTOMER_SAFE
        ):
            return (
                "Production schedule is at risk but the "
                "required date remains safe"
            )

        if (
            decision
            == ETARiskDecision.CUSTOMER_DATE_AT_RISK
        ):
            return (
                "The required date is at risk"
            )

        if (
            decision
            == ETARiskDecision.CUSTOMER_DATE_LATE
        ):
            return (
                "The required date is expected to be missed"
            )

        if (
            decision
            == ETARiskDecision.REQUIRED_DATE_CONFLICT
        ):
            return (
                "The current ETA conflicts with the "
                "required date despite the internal "
                "schedule appearing on track"
            )

        return (
            "ETA risk status requires review"
        )

    # ============================================================
    # CONVENIENCE ACCESSORS
    # ============================================================

    def decision(
        self,
        *,
        schedule_risk: ETAScheduleVariance,
        required_date_risk: RequiredDateRisk,
    ) -> ETARiskDecision:
        """
        Return only the operational decision.
        """

        return self.calculate(
            schedule_risk=schedule_risk,
            required_date_risk=required_date_risk,
        ).decision

    def summary(
        self,
        *,
        schedule_risk: ETAScheduleVariance,
        required_date_risk: RequiredDateRisk,
    ) -> str:
        """
        Return only the operational summary text.
        """

        return self.calculate(
            schedule_risk=schedule_risk,
            required_date_risk=required_date_risk,
        ).summary

    def action_required(
        self,
        *,
        schedule_risk: ETAScheduleVariance,
        required_date_risk: RequiredDateRisk,
    ) -> bool:
        """
        Return whether operational attention is required.
        """

        return self.calculate(
            schedule_risk=schedule_risk,
            required_date_risk=required_date_risk,
        ).action_required