from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional

from .models import ETAStatus


class ETARiskLevel(str, Enum):
    """
    Schedule-risk classification for a Manufacturing Order.

    This is deliberately separate from ETAStatus.

    ETAStatus describes the current ETA state.

    ETARiskLevel describes the degree of schedule variance.
    """

    UNKNOWN = "UNKNOWN"
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    LATE = "LATE"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class ETAScheduleVariance:
    """
    Represents the difference between the planned ETA and the
    current/live ETA.

    Positive variance:
        Current ETA is later than planned.

    Negative variance:
        Current ETA is earlier than planned.

    Zero variance:
        Current ETA matches planned ETA.
    """

    planned_eta: Optional[datetime]
    current_eta: Optional[datetime]
    variance: Optional[timedelta]
    variance_hours: Optional[Decimal]
    risk_level: ETARiskLevel
    status: ETAStatus
    reason: str

    @property
    def is_ahead(self) -> bool:
        """
        True when the live ETA is earlier than the planned ETA.
        """

        if self.variance is None:
            return False

        return self.variance < timedelta(0)

    @property
    def is_on_schedule(self) -> bool:
        """
        True when the live ETA exactly matches the planned ETA.
        """

        if self.variance is None:
            return False

        return self.variance == timedelta(0)

    @property
    def is_behind(self) -> bool:
        """
        True when the live ETA is later than the planned ETA.
        """

        if self.variance is None:
            return False

        return self.variance > timedelta(0)


@dataclass(frozen=True)
class ETARiskThresholds:
    """
    Configurable schedule-risk thresholds.

    The thresholds are deliberately expressed in hours so the
    Production module remains independent of UI or database
    representations.

    Example:

        4 hours:
            <= 4 hours late  -> ON_TRACK

        8 hours:
            > 4 and <= 8     -> AT_RISK

        > 8 hours:
            LATE
    """

    at_risk_hours: Decimal = Decimal("4")
    late_hours: Decimal = Decimal("8")

    def __post_init__(self) -> None:
        at_risk = Decimal(
            str(self.at_risk_hours)
        )

        late = Decimal(
            str(self.late_hours)
        )

        if at_risk < Decimal("0"):
            raise ValueError(
                "at_risk_hours cannot be negative"
            )

        if late <= Decimal("0"):
            raise ValueError(
                "late_hours must be greater than zero"
            )

        if late <= at_risk:
            raise ValueError(
                "late_hours must be greater than "
                "at_risk_hours"
            )


class ETARiskCalculator:
    """
    Calculates schedule variance and ETA risk.

    This component:

        Planned ETA
             +
        Current/Live ETA
             ↓
        Schedule Variance
             ↓
        Risk Classification

    It does not modify ETAPlan or ManufacturingOrder.

    It is therefore safe to use for dashboards, status boards,
    reporting and future management alerts without creating
    side effects.
    """

    def __init__(
        self,
        thresholds: Optional[
            ETARiskThresholds
        ] = None,
    ) -> None:
        self.thresholds = (
            thresholds
            or ETARiskThresholds()
        )

    # ============================================================
    # SCHEDULE VARIANCE
    # ============================================================

    def calculate_variance(
        self,
        *,
        planned_eta: Optional[datetime],
        current_eta: Optional[datetime],
        status: ETAStatus = ETAStatus.UNKNOWN,
    ) -> ETAScheduleVariance:
        """
        Calculate schedule variance.

        Formula:

            Current ETA - Planned ETA

        Therefore:

            negative = ahead
            zero     = exactly on plan
            positive = behind
        """

        if status == ETAStatus.COMPLETED:
            return ETAScheduleVariance(
                planned_eta=planned_eta,
                current_eta=current_eta,
                variance=(
                    current_eta - planned_eta
                    if (
                        planned_eta is not None
                        and current_eta is not None
                    )
                    else None
                ),
                variance_hours=(
                    self._timedelta_to_hours(
                        current_eta - planned_eta
                    )
                    if (
                        planned_eta is not None
                        and current_eta is not None
                    )
                    else None
                ),
                risk_level=ETARiskLevel.COMPLETED,
                status=ETAStatus.COMPLETED,
                reason=(
                    "Manufacturing Order is completed"
                ),
            )

        if (
            planned_eta is None
            or current_eta is None
        ):
            return ETAScheduleVariance(
                planned_eta=planned_eta,
                current_eta=current_eta,
                variance=None,
                variance_hours=None,
                risk_level=(
                    ETARiskLevel.UNKNOWN
                ),
                status=status,
                reason=(
                    "Planned ETA or current ETA "
                    "is not available"
                ),
            )

        variance = (
            current_eta - planned_eta
        )

        variance_hours = (
            self._timedelta_to_hours(
                variance
            )
        )

        risk_level = (
            self._classify_variance(
                variance_hours
            )
        )

        resolved_status = self._resolve_status(
            status=status,
            variance_hours=variance_hours,
            risk_level=risk_level,
        )

        reason = (
            self._build_reason(
                variance_hours=variance_hours,
                risk_level=risk_level,
            )
        )

        return ETAScheduleVariance(
            planned_eta=planned_eta,
            current_eta=current_eta,
            variance=variance,
            variance_hours=variance_hours,
            risk_level=risk_level,
            status=resolved_status,
            reason=reason,
        )

    # ============================================================
    # RISK CLASSIFICATION
    # ============================================================

    def classify(
        self,
        *,
        planned_eta: Optional[datetime],
        current_eta: Optional[datetime],
        status: ETAStatus = ETAStatus.UNKNOWN,
    ) -> ETARiskLevel:
        """
        Return only the schedule-risk classification.
        """

        result = self.calculate_variance(
            planned_eta=planned_eta,
            current_eta=current_eta,
            status=status,
        )

        return result.risk_level

    def _classify_variance(
        self,
        variance_hours: Decimal,
    ) -> ETARiskLevel:
        """
        Classify positive schedule variance.

        Being ahead of schedule is considered ON_TRACK.

        A delay up to the configured at-risk threshold is also
        considered ON_TRACK.

        A delay greater than the at-risk threshold but within the
        late threshold is AT_RISK.

        A delay beyond the late threshold is LATE.
        """

        if variance_hours <= self.thresholds.at_risk_hours:
            return ETARiskLevel.ON_TRACK

        if variance_hours <= self.thresholds.late_hours:
            return ETARiskLevel.AT_RISK

        return ETARiskLevel.LATE

    def _resolve_status(
        self,
        *,
        status: ETAStatus,
        variance_hours: Decimal,
        risk_level: ETARiskLevel,
    ) -> ETAStatus:
        """
        Preserve lifecycle states that should not be replaced by
        schedule-risk classification.

        For example:

            MATERIAL_WAIT remains MATERIAL_WAIT
            NOT_STARTED remains NOT_STARTED
            COMPLETED remains COMPLETED

        Once active schedule variance exists, ON_TRACK / AT_RISK /
        LATE are returned according to the calculated variance.
        """

        if status == ETAStatus.COMPLETED:
            return ETAStatus.COMPLETED

        if status == ETAStatus.MATERIAL_WAIT:
            return ETAStatus.MATERIAL_WAIT

        if status == ETAStatus.NOT_STARTED:
            return ETAStatus.NOT_STARTED

        if status == ETAStatus.UNKNOWN:
            return ETAStatus.UNKNOWN

        if risk_level == ETARiskLevel.LATE:
            return ETAStatus.LATE

        if risk_level == ETARiskLevel.AT_RISK:
            return ETAStatus.AT_RISK

        return ETAStatus.ON_TRACK

    # ============================================================
    # TIME CONVERSION
    # ============================================================

    @staticmethod
    def _timedelta_to_hours(
        value: timedelta,
    ) -> Decimal:
        """
        Convert timedelta to Decimal hours without losing the
        precision needed for schedule calculations.
        """

        return (
            Decimal(
                str(
                    value.total_seconds()
                )
            )
            / Decimal("3600")
        )

    # ============================================================
    # HUMAN-READABLE REASON
    # ============================================================

    @staticmethod
    def _build_reason(
        *,
        variance_hours: Decimal,
        risk_level: ETARiskLevel,
    ) -> str:
        """
        Build an audit-friendly explanation for the calculated
        schedule state.
        """

        if variance_hours < Decimal("0"):
            return (
                "Live ETA is ahead of the planned ETA"
            )

        if variance_hours == Decimal("0"):
            return (
                "Live ETA matches the planned ETA"
            )

        if risk_level == ETARiskLevel.ON_TRACK:
            return (
                "Live ETA is later than planned but "
                "remains within the acceptable schedule "
                "variance threshold"
            )

        if risk_level == ETARiskLevel.AT_RISK:
            return (
                "Live ETA has moved beyond the normal "
                "schedule variance threshold"
            )

        if risk_level == ETARiskLevel.LATE:
            return (
                "Live ETA has exceeded the late schedule "
                "variance threshold"
            )

        return (
            "Schedule variance could not be classified"
        )