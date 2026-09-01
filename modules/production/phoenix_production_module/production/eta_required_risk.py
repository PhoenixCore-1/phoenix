from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional


class RequiredDateRiskLevel(str, Enum):
    """
    Risk classification against the required/customer date.

    This is deliberately separate from ETARiskLevel.

    ETARiskLevel answers:
        "Are we behind the internal production plan?"

    RequiredDateRiskLevel answers:
        "Can we meet the required date?"
    """

    UNKNOWN = "UNKNOWN"
    ON_TIME = "ON_TIME"
    AT_RISK = "AT_RISK"
    LATE = "LATE"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class RequiredDateRiskThresholds:
    """
    Configurable buffer before the required date becomes AT_RISK.

    Example:

        24 hours:
            Live ETA up to 24 hours before required date
            -> ON_TIME

            Live ETA less than 24 hours before required date
            -> AT_RISK

            Live ETA after required date
            -> LATE
    """

    at_risk_buffer_hours: Decimal = Decimal("24")

    def __post_init__(self) -> None:
        buffer_hours = Decimal(
            str(self.at_risk_buffer_hours)
        )

        if buffer_hours < Decimal("0"):
            raise ValueError(
                "at_risk_buffer_hours cannot be negative"
            )


@dataclass(frozen=True)
class RequiredDateRisk:
    """
    Represents the difference between Live ETA and the required
    date.

    Formula:

        Live ETA - Required Date

    Therefore:

        negative = before required date
        zero     = exactly on required date
        positive = after required date
    """

    required_date: Optional[datetime]
    current_eta: Optional[datetime]
    variance: Optional[timedelta]
    variance_hours: Optional[Decimal]
    risk_level: RequiredDateRiskLevel
    reason: str

    @property
    def can_meet_required_date(self) -> bool:
        """
        True when the current ETA is on or before the required
        date.
        """

        if self.variance is None:
            return False

        return self.variance <= timedelta(0)

    @property
    def is_before_required_date(self) -> bool:
        """
        True when the Live ETA is earlier than the required date.
        """

        if self.variance is None:
            return False

        return self.variance < timedelta(0)

    @property
    def is_exactly_required_date(self) -> bool:
        """
        True when Live ETA exactly matches required date.
        """

        if self.variance is None:
            return False

        return self.variance == timedelta(0)

    @property
    def is_after_required_date(self) -> bool:
        """
        True when Live ETA is later than the required date.
        """

        if self.variance is None:
            return False

        return self.variance > timedelta(0)


class RequiredDateRiskCalculator:
    """
    Calculates customer/required-date risk.

    This component does not modify ManufacturingOrder or ETAPlan.

    It is deliberately independent from internal schedule risk.

    Internal schedule risk:
        Live ETA vs Planned ETA

    Required-date risk:
        Live ETA vs Required Date
    """

    def __init__(
        self,
        thresholds: Optional[
            RequiredDateRiskThresholds
        ] = None,
    ) -> None:
        self.thresholds = (
            thresholds
            or RequiredDateRiskThresholds()
        )

    # ============================================================
    # REQUIRED-DATE VARIANCE
    # ============================================================

    def calculate(
        self,
        *,
        required_date: Optional[datetime],
        current_eta: Optional[datetime],
        completed: bool = False,
    ) -> RequiredDateRisk:
        """
        Calculate required-date variance and risk.

        Formula:

            current_eta - required_date
        """

        if completed:
            return RequiredDateRisk(
                required_date=required_date,
                current_eta=current_eta,
                variance=(
                    current_eta - required_date
                    if (
                        required_date is not None
                        and current_eta is not None
                    )
                    else None
                ),
                variance_hours=(
                    self._timedelta_to_hours(
                        current_eta - required_date
                    )
                    if (
                        required_date is not None
                        and current_eta is not None
                    )
                    else None
                ),
                risk_level=(
                    RequiredDateRiskLevel.COMPLETED
                ),
                reason=(
                    "Manufacturing Order is completed"
                ),
            )

        from datetime import timezone

        # Preserve caller/domain values.
        # Only calculation copies are normalized.
        calculation_required_date = required_date
        calculation_current_eta = current_eta

        if (
            calculation_required_date is not None
            and calculation_required_date.tzinfo is None
        ):
            calculation_required_date = (
                calculation_required_date.replace(
                    tzinfo=timezone.utc
                )
            )

        if (
            calculation_current_eta is not None
            and calculation_current_eta.tzinfo is None
        ):
            calculation_current_eta = (
                calculation_current_eta.replace(
                    tzinfo=timezone.utc
                )
            )

        if (
            calculation_required_date is None
            or calculation_current_eta is None
        ):
            return RequiredDateRisk(
                required_date=required_date,
                current_eta=current_eta,
                variance=None,
                variance_hours=None,
                risk_level=RequiredDateRiskLevel.UNKNOWN,
                reason=(
                    "Required date or current ETA "
                    "is not available"
                ),
            )

        variance = (
            calculation_current_eta
            - calculation_required_date
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

        reason = (
            self._build_reason(
                variance_hours=variance_hours,
                risk_level=risk_level,
            )
        )

        return RequiredDateRisk(
            required_date=required_date,
            current_eta=current_eta,
            variance=variance,
            variance_hours=variance_hours,
            risk_level=risk_level,
            reason=reason,
        )

    # ============================================================
    # RISK CLASSIFICATION
    # ============================================================

    def classify(
        self,
        *,
        required_date: Optional[datetime],
        current_eta: Optional[datetime],
        completed: bool = False,
    ) -> RequiredDateRiskLevel:
        """
        Return only the required-date risk level.
        """

        result = self.calculate(
            required_date=required_date,
            current_eta=current_eta,
            completed=completed,
        )

        return result.risk_level

    def _classify_variance(
        self,
        variance_hours: Decimal,
    ) -> RequiredDateRiskLevel:
        """
        Classify the required-date variance.

        Negative variance means the order is due before the
        required date.

        A configurable buffer is used to identify orders that are
        approaching the required date.
        """

        if variance_hours > Decimal("0"):
            return RequiredDateRiskLevel.LATE

        remaining_hours = (
            abs(variance_hours)
        )

        if (
            remaining_hours
            <= self.thresholds.at_risk_buffer_hours
        ):
            return RequiredDateRiskLevel.AT_RISK

        return RequiredDateRiskLevel.ON_TIME

    # ============================================================
    # REASON
    # ============================================================

    @staticmethod
    def _build_reason(
        *,
        variance_hours: Decimal,
        risk_level: RequiredDateRiskLevel,
    ) -> str:
        if variance_hours > Decimal("0"):
            return (
                "Live ETA is later than the required date"
            )

        if variance_hours == Decimal("0"):
            return (
                "Live ETA falls exactly on the required date"
            )

        if risk_level == RequiredDateRiskLevel.AT_RISK:
            return (
                "Live ETA is before the required date but "
                "inside the required-date risk buffer"
            )

        return (
            "Live ETA is sufficiently before the required date"
        )

    # ============================================================
    # TIME CONVERSION
    # ============================================================

    @staticmethod
    def _timedelta_to_hours(
        value: timedelta,
    ) -> Decimal:
        return (
            Decimal(
                str(
                    value.total_seconds()
                )
            )
            / Decimal("3600")
        )