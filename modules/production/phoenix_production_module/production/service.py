from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from .commands import (
    complete,
    hold,
    record_quantity,
    record_stage_quantity,
    release,
    resume,
    start,
)
from .eta_operational_snapshot import (
    ETAOperationalSnapshot,
)
from .eta_required_risk import (
    RequiredDateRisk,
    RequiredDateRiskCalculator,
    RequiredDateRiskLevel,
    RequiredDateRiskThresholds,
)
from .eta_risk import (
    ETARiskCalculator,
    ETARiskLevel,
    ETAScheduleVariance,
    ETARiskThresholds,
)
from .eta_risk_summary import (
    ETARiskSummary,
    ETARiskSummaryCalculator,
)
from .models import (
    ETAStatus,
    ETASnapshot,
    ManufacturingOrder,
    MaterialRequirement,
)
from .state_machine import TransitionResult


class RateConfidence(str, Enum):
    """
    Confidence level assigned to the production-rate estimate.
    """

    INSUFFICIENT = "INSUFFICIENT"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class RateSelection:
    """
    Result of the production-rate selection process.
    """

    selected_rate: Optional[Decimal]
    full_history_rate: Optional[Decimal]
    rolling_rate: Optional[Decimal]
    confidence: RateConfidence
    source: str
    history_hours: Decimal
    rolling_window_hours: Decimal
    reason: str


class ProductionService:
    """
    Application service for the Phoenix Production module.

    This layer orchestrates Production domain commands and ETA
    calculations.

    It does not access the database directly.

    Domain rules remain in:
        models.py
        commands.py
        state_machine.py
        eta_risk.py
        eta_required_risk.py
        eta_risk_summary.py

    Core persistence remains behind:
        core_adapter.py
    """

    # ============================================================
    # PRODUCTION LIFECYCLE
    # ============================================================

    def release_order(
        self,
        order: ManufacturingOrder,
        now: Optional[datetime] = None,
    ) -> TransitionResult:
        return release(order, now=now)

    def start_order(
        self,
        order: ManufacturingOrder,
        now: Optional[datetime] = None,
    ) -> TransitionResult:
        result = start(order, now=now)

        if order.started_at is not None:
            order.eta.mark_production_started(
                order.started_at
            )

        return result

    def hold_order(
        self,
        order: ManufacturingOrder,
        reason: str,
        now: Optional[datetime] = None,
    ) -> TransitionResult:
        return hold(
            order,
            reason=reason,
            now=now,
        )

    def resume_order(
        self,
        order: ManufacturingOrder,
        now: Optional[datetime] = None,
    ) -> TransitionResult:
        return resume(order, now=now)

    def record_quantity(
        self,
        order: ManufacturingOrder,
        *,
        accepted: Decimal = Decimal("0"),
        rejected: Decimal = Decimal("0"),
        rework: Decimal = Decimal("0"),
    ) -> None:
        record_quantity(
            order,
            accepted=accepted,
            rejected=rejected,
            rework=rework,
        )

    def record_stage_quantity(
        self,
        order: ManufacturingOrder,
        stage,
        *,
        accepted: Decimal = Decimal("0"),
        rejected: Decimal = Decimal("0"),
        rework: Decimal = Decimal("0"),
    ) -> None:
        record_stage_quantity(
            order,
            stage,
            accepted=accepted,
            rejected=rejected,
            rework=rework,
        )

    def complete_order(
        self,
        order: ManufacturingOrder,
        now: Optional[datetime] = None,
    ) -> TransitionResult:
        result = complete(order, now=now)

        if order.completed_at is not None:
            order.eta.mark_completed(
                order.completed_at
            )

        return result

    # ============================================================
    # MATERIAL / PLANNING ETA
    # ============================================================

    def add_material_requirement(
        self,
        order: ManufacturingOrder,
        material: MaterialRequirement,
    ) -> None:
        order.add_material_requirement(material)
        order.calculate_material_ready_date()

    def calculate_material_ready_date(
        self,
        order: ManufacturingOrder,
    ) -> Optional[datetime]:
        return order.calculate_material_ready_date()

    def establish_planned_eta(
        self,
        order: ManufacturingOrder,
        *,
        planned_production_start: Optional[datetime],
        planned_eta: Optional[datetime],
    ) -> None:
        order.eta.establish_planned_eta(
            planned_production_start=planned_production_start,
            planned_eta=planned_eta,
        )

    def calculate_planned_production_start(
        self,
        order: ManufacturingOrder,
    ) -> Optional[datetime]:
        material_ready = (
            self.calculate_material_ready_date(order)
        )

        if material_ready is None:
            return None

        order.eta.planned_production_start = (
            material_ready
        )

        return material_ready

    def calculate_planned_eta_from_duration(
        self,
        order: ManufacturingOrder,
        *,
        production_duration_hours: Decimal,
    ) -> Optional[datetime]:
        production_duration_hours = Decimal(
            str(production_duration_hours)
        )

        if production_duration_hours < 0:
            raise ValueError(
                "production_duration_hours cannot be negative"
            )

        start_date = (
            order.eta.planned_production_start
            or order.eta.material_ready_date
        )

        if start_date is None:
            return None

        planned_eta = (
            start_date
            + timedelta(
                hours=float(
                    production_duration_hours
                )
            )
        )

        order.eta.establish_planned_eta(
            planned_production_start=start_date,
            planned_eta=planned_eta,
        )

        return planned_eta

    # ============================================================
    # PRODUCTION START
    # ============================================================

    def mark_production_started(
        self,
        order: ManufacturingOrder,
        started_at: datetime,
    ) -> None:
        """
        Establish actual production start for ETA tracking.
        """

        if order.state.value == "PLANNED":
            release(
                order,
                now=started_at,
            )

        if order.state.value == "RELEASED":
            start(
                order,
                now=started_at,
            )

        if order.started_at is None:
            order.started_at = started_at

        order.eta.mark_production_started(
            started_at
        )

    # ============================================================
    # 1.3.13 ACTUAL PRODUCTION RATE
    # ============================================================

    def calculate_actual_production_rate(
        self,
        order: ManufacturingOrder,
        *,
        calculated_at: Optional[datetime] = None,
    ) -> Optional[Decimal]:
        """
        Calculate actual production throughput from the entire
        Manufacturing Order history.
        """

        started_at = (
            order.eta.actual_production_start
        )

        if started_at is None:
            return None

        calculated_at = (
            calculated_at
            or datetime.now(timezone.utc)
        )

        if calculated_at < started_at:
            raise ValueError(
                "calculated_at cannot be before "
                "actual production start"
            )

        elapsed = calculated_at - started_at

        effective_hold = (
            order.eta.effective_hold_duration
        )

        effective_production_time = (
            elapsed - effective_hold
        )

        if effective_production_time <= timedelta(0):
            return None

        processed_quantity = (
            order.quantity.processed
        )

        if processed_quantity <= Decimal("0"):
            return None

        hours = (
            Decimal(
                str(
                    effective_production_time.total_seconds()
                )
            )
            / Decimal("3600")
        )

        if hours <= Decimal("0"):
            return None

        return processed_quantity / hours

    def calculate_actual_production_rate_from_window(
        self,
        order: ManufacturingOrder,
        *,
        window_start: datetime,
        window_end: Optional[datetime] = None,
        quantity_produced: Optional[Decimal] = None,
    ) -> Optional[Decimal]:
        """
        Calculate production rate over a defined window.
        """

        window_end = (
            window_end
            or datetime.now(timezone.utc)
        )

        if window_end < window_start:
            raise ValueError(
                "window_end cannot be before window_start"
            )

        if quantity_produced is None:
            quantity_produced = (
                order.quantity.processed
            )

        quantity_produced = Decimal(
            str(quantity_produced)
        )

        if quantity_produced < Decimal("0"):
            raise ValueError(
                "quantity_produced cannot be negative"
            )

        duration = window_end - window_start

        if duration <= timedelta(0):
            return None

        hours = (
            Decimal(
                str(
                    duration.total_seconds()
                )
            )
            / Decimal("3600")
        )

        if hours <= Decimal("0"):
            return None

        if quantity_produced == Decimal("0"):
            return Decimal("0")

        return quantity_produced / hours

    # ============================================================
    # 1.3.14 ROLLING PRODUCTION RATE
    # ============================================================

    def calculate_rolling_production_rate(
        self,
        order: ManufacturingOrder,
        *,
        window_hours: Decimal,
        calculated_at: Optional[datetime] = None,
        quantity_produced: Optional[Decimal] = None,
    ) -> Optional[Decimal]:
        """
        Calculate recent rolling production throughput.
        """

        window_hours = Decimal(
            str(window_hours)
        )

        if window_hours <= Decimal("0"):
            raise ValueError(
                "window_hours must be greater than zero"
            )

        started_at = (
            order.eta.actual_production_start
        )

        if started_at is None:
            return None

        calculated_at = (
            calculated_at
            or datetime.now(timezone.utc)
        )

        if calculated_at < started_at:
            raise ValueError(
                "calculated_at cannot be before "
                "actual production start"
            )

        requested_window = timedelta(
            hours=float(window_hours)
        )

        window_start = (
            calculated_at - requested_window
        )

        if window_start < started_at:
            window_start = started_at

        actual_window_duration = (
            calculated_at - window_start
        )

        if actual_window_duration <= timedelta(0):
            return None

        if quantity_produced is None:
            quantity_produced = (
                order.quantity.processed
            )

        quantity_produced = Decimal(
            str(quantity_produced)
        )

        if quantity_produced < Decimal("0"):
            raise ValueError(
                "quantity_produced cannot be negative"
            )

        if quantity_produced == Decimal("0"):
            return Decimal("0")

        hold_duration = (
            order.eta.total_hold_duration
        )

        if order.eta.hold_is_active:
            hold_duration += (
                order.eta.current_hold_duration
            )

        if hold_duration > actual_window_duration:
            hold_duration = actual_window_duration

        effective_window = (
            actual_window_duration
            - hold_duration
        )

        if effective_window <= timedelta(0):
            return None

        effective_hours = (
            Decimal(
                str(
                    effective_window.total_seconds()
                )
            )
            / Decimal("3600")
        )

        if effective_hours <= Decimal("0"):
            return None

        return quantity_produced / effective_hours

    # ============================================================
    # 1.3.15 ETA CONFIDENCE & RATE SELECTION
    # ============================================================

    def evaluate_rate_confidence(
        self,
        order: ManufacturingOrder,
        *,
        calculated_at: Optional[datetime] = None,
        rolling_window_hours: Decimal = Decimal("4"),
        quantity_produced: Optional[Decimal] = None,
        minimum_history_hours: Decimal = Decimal("4"),
        high_confidence_hours: Decimal = Decimal("8"),
        minimum_quantity: Decimal = Decimal("1"),
    ) -> RateSelection:
        """
        Evaluate the quality of available production-rate history.
        """

        calculated_at = (
            calculated_at
            or datetime.now(timezone.utc)
        )

        minimum_history_hours = Decimal(
            str(minimum_history_hours)
        )

        high_confidence_hours = Decimal(
            str(high_confidence_hours)
        )

        minimum_quantity = Decimal(
            str(minimum_quantity)
        )

        rolling_window_hours = Decimal(
            str(rolling_window_hours)
        )

        if minimum_history_hours <= Decimal("0"):
            raise ValueError(
                "minimum_history_hours must be greater than zero"
            )

        if high_confidence_hours < minimum_history_hours:
            raise ValueError(
                "high_confidence_hours cannot be less than "
                "minimum_history_hours"
            )

        if rolling_window_hours <= Decimal("0"):
            raise ValueError(
                "rolling_window_hours must be greater than zero"
            )

        started_at = (
            order.eta.actual_production_start
        )

        if started_at is None:
            return RateSelection(
                selected_rate=None,
                full_history_rate=None,
                rolling_rate=None,
                confidence=RateConfidence.INSUFFICIENT,
                source="NONE",
                history_hours=Decimal("0"),
                rolling_window_hours=rolling_window_hours,
                reason=(
                    "Production has not started"
                ),
            )

        if calculated_at < started_at:
            raise ValueError(
                "calculated_at cannot be before "
                "actual production start"
            )

        elapsed = (
            calculated_at - started_at
        )

        effective_hold = (
            order.eta.effective_hold_duration
        )

        effective_history = (
            elapsed - effective_hold
        )

        if effective_history <= timedelta(0):
            return RateSelection(
                selected_rate=None,
                full_history_rate=None,
                rolling_rate=None,
                confidence=RateConfidence.INSUFFICIENT,
                source="NONE",
                history_hours=Decimal("0"),
                rolling_window_hours=rolling_window_hours,
                reason=(
                    "No effective production history is available"
                ),
            )

        history_hours = (
            Decimal(
                str(
                    effective_history.total_seconds()
                )
            )
            / Decimal("3600")
        )

        if quantity_produced is None:
            quantity_produced = (
                order.quantity.processed
            )

        quantity_produced = Decimal(
            str(quantity_produced)
        )

        if quantity_produced < minimum_quantity:
            return RateSelection(
                selected_rate=None,
                full_history_rate=None,
                rolling_rate=None,
                confidence=RateConfidence.INSUFFICIENT,
                source="NONE",
                history_hours=history_hours,
                rolling_window_hours=rolling_window_hours,
                reason=(
                    "Insufficient production quantity "
                    "for a reliable rate"
                ),
            )

        full_history_rate = (
            self.calculate_actual_production_rate(
                order,
                calculated_at=calculated_at,
            )
        )

        rolling_rate = (
            self.calculate_rolling_production_rate(
                order,
                window_hours=rolling_window_hours,
                calculated_at=calculated_at,
                quantity_produced=quantity_produced,
            )
        )

        if history_hours < minimum_history_hours:
            return RateSelection(
                selected_rate=full_history_rate,
                full_history_rate=full_history_rate,
                rolling_rate=rolling_rate,
                confidence=RateConfidence.INSUFFICIENT,
                source="FULL_HISTORY"
                if full_history_rate is not None
                else "NONE",
                history_hours=history_hours,
                rolling_window_hours=rolling_window_hours,
                reason=(
                    "Production history is below the minimum "
                    "confidence threshold"
                ),
            )

        if history_hours < high_confidence_hours:
            return RateSelection(
                selected_rate=full_history_rate,
                full_history_rate=full_history_rate,
                rolling_rate=rolling_rate,
                confidence=RateConfidence.LOW,
                source="FULL_HISTORY"
                if full_history_rate is not None
                else "NONE",
                history_hours=history_hours,
                rolling_window_hours=rolling_window_hours,
                reason=(
                    "Production has enough history for a "
                    "baseline rate but not enough for high "
                    "confidence"
                ),
            )

        if (
            rolling_rate is not None
            and rolling_rate > Decimal("0")
        ):
            return RateSelection(
                selected_rate=rolling_rate,
                full_history_rate=full_history_rate,
                rolling_rate=rolling_rate,
                confidence=RateConfidence.HIGH,
                source="ROLLING",
                history_hours=history_hours,
                rolling_window_hours=rolling_window_hours,
                reason=(
                    "Sufficient production history exists; "
                    "recent rolling throughput is preferred"
                ),
            )

        return RateSelection(
            selected_rate=full_history_rate,
            full_history_rate=full_history_rate,
            rolling_rate=rolling_rate,
            confidence=RateConfidence.MEDIUM,
            source="FULL_HISTORY"
            if full_history_rate is not None
            else "NONE",
            history_hours=history_hours,
            rolling_window_hours=rolling_window_hours,
            reason=(
                "Rolling rate is unavailable; full-history "
                "rate remains the fallback"
            ),
        )

    def select_eta_production_rate(
        self,
        order: ManufacturingOrder,
        *,
        calculated_at: Optional[datetime] = None,
        rolling_window_hours: Decimal = Decimal("4"),
        quantity_produced: Optional[Decimal] = None,
        minimum_history_hours: Decimal = Decimal("4"),
        high_confidence_hours: Decimal = Decimal("8"),
        minimum_quantity: Decimal = Decimal("1"),
    ) -> RateSelection:
        """
        Public rate-selection entry point for ETA calculation.
        """

        return self.evaluate_rate_confidence(
            order,
            calculated_at=calculated_at,
            rolling_window_hours=rolling_window_hours,
            quantity_produced=quantity_produced,
            minimum_history_hours=minimum_history_hours,
            high_confidence_hours=high_confidence_hours,
            minimum_quantity=minimum_quantity,
        )

    # ============================================================
    # 1.3.15 LIVE ETA USING SELECTED RATE
    # ============================================================

    def calculate_live_eta_from_selected_rate(
        self,
        order: ManufacturingOrder,
        *,
        calculated_at: Optional[datetime] = None,
        rolling_window_hours: Decimal = Decimal("4"),
        quantity_produced: Optional[Decimal] = None,
        minimum_history_hours: Decimal = Decimal("4"),
        high_confidence_hours: Decimal = Decimal("8"),
        minimum_quantity: Decimal = Decimal("1"),
    ) -> Optional[ETASnapshot]:
        """
        Calculate Live ETA using the production-rate selection
        policy.
        """

        calculated_at = (
            calculated_at
            or datetime.now(timezone.utc)
        )

        selection = (
            self.select_eta_production_rate(
                order,
                calculated_at=calculated_at,
                rolling_window_hours=rolling_window_hours,
                quantity_produced=quantity_produced,
                minimum_history_hours=minimum_history_hours,
                high_confidence_hours=high_confidence_hours,
                minimum_quantity=minimum_quantity,
            )
        )

        if selection.selected_rate is None:
            return None

        if selection.selected_rate <= Decimal("0"):
            return None

        remaining_quantity = (
            order.quantity.remaining
        )

        if remaining_quantity <= Decimal("0"):
            order.eta.mark_completed(
                calculated_at
            )

            return ETASnapshot(
                calculated_at=calculated_at,
                planned_eta=order.eta.planned_eta,
                current_eta=order.eta.current_eta,
                required_date=order.eta.required_date,
                status=ETAStatus.COMPLETED,
                reason=(
                    "Production quantity is complete"
                ),
            )

        remaining_hours = (
            remaining_quantity
            / selection.selected_rate
        )

        live_eta = (
            calculated_at
            + timedelta(
                hours=float(
                    remaining_hours
                )
            )
        )

        return order.eta.update_current_eta(
            live_eta,
            calculated_at=calculated_at,
            reason=(
                "Live ETA calculated using "
                f"{selection.source.lower()} production rate "
                f"with {selection.confidence.value.lower()} "
                "confidence"
            ),
        )

    # ============================================================
    # 1.3.16 ETA RISK CALCULATOR
    # ============================================================

    def calculate_eta_schedule_variance(
        self,
        order: ManufacturingOrder,
        *,
        planned_eta: Optional[datetime] = None,
        current_eta: Optional[datetime] = None,
        status: Optional[ETAStatus] = None,
        risk_thresholds: Optional[
            ETARiskThresholds
        ] = None,
    ) -> ETAScheduleVariance:
        """
        Calculate the Manufacturing Order's internal schedule
        variance and ETA risk.

        Defaults:

            planned_eta
                -> order.eta.planned_eta

            current_eta
                -> order.eta.current_eta

            status
                -> order.eta.status

        This method is read-only.
        """

        resolved_planned_eta = (
            planned_eta
            if planned_eta is not None
            else order.eta.planned_eta
        )

        resolved_current_eta = (
            current_eta
            if current_eta is not None
            else order.eta.current_eta
        )

        resolved_status = (
            status
            if status is not None
            else order.eta.status
        )

        calculator = ETARiskCalculator(
            thresholds=risk_thresholds
        )

        return calculator.calculate_variance(
            planned_eta=resolved_planned_eta,
            current_eta=resolved_current_eta,
            status=resolved_status,
        )

    def get_eta_risk_level(
        self,
        order: ManufacturingOrder,
        *,
        risk_thresholds: Optional[
            ETARiskThresholds
        ] = None,
    ) -> ETARiskLevel:
        """
        Return only the internal schedule risk level.
        """

        result = self.calculate_eta_schedule_variance(
            order,
            risk_thresholds=risk_thresholds,
        )

        return result.risk_level

    def calculate_eta_status(
        self,
        order: ManufacturingOrder,
        *,
        risk_thresholds: Optional[
            ETARiskThresholds
        ] = None,
    ) -> ETAStatus:
        """
        Return the schedule-aware ETA status.

        This is read-only and does not overwrite the order status.
        """

        result = self.calculate_eta_schedule_variance(
            order,
            risk_thresholds=risk_thresholds,
        )

        return result.status

    # ============================================================
    # 1.3.18 REQUIRED-DATE RISK
    # ============================================================

    def calculate_required_date_risk(
        self,
        order: ManufacturingOrder,
        *,
        required_date: Optional[datetime] = None,
        current_eta: Optional[datetime] = None,
        completed: Optional[bool] = None,
        risk_thresholds: Optional[
            RequiredDateRiskThresholds
        ] = None,
    ) -> RequiredDateRisk:
        """
        Calculate customer/required-date risk for a
        Manufacturing Order.

        Defaults:

            required_date
                -> order.eta.required_date

            current_eta
                -> order.eta.current_eta

            completed
                -> derived from order state when not explicitly
                   supplied

        This method is read-only.

        It does not modify the Manufacturing Order.
        """

        resolved_required_date = (
            required_date
            if required_date is not None
            else order.eta.required_date
        )

        resolved_current_eta = (
            current_eta
            if current_eta is not None
            else order.eta.current_eta
        )

        if completed is None:
            completed = (
                order.state.value == "COMPLETED"
                or order.eta.status == ETAStatus.COMPLETED
            )

        calculator = RequiredDateRiskCalculator(
            thresholds=risk_thresholds
        )

        return calculator.calculate(
            required_date=resolved_required_date,
            current_eta=resolved_current_eta,
            completed=completed,
        )

    def get_required_date_risk_level(
        self,
        order: ManufacturingOrder,
        *,
        risk_thresholds: Optional[
            RequiredDateRiskThresholds
        ] = None,
    ) -> RequiredDateRiskLevel:
        """
        Return only the customer/required-date risk level.
        """

        result = self.calculate_required_date_risk(
            order,
            risk_thresholds=risk_thresholds,
        )

        return result.risk_level

    def can_meet_required_date(
        self,
        order: ManufacturingOrder,
        *,
        risk_thresholds: Optional[
            RequiredDateRiskThresholds
        ] = None,
    ) -> bool:
        """
        Return True when the current ETA is on or before the
        required date.
        """

        result = self.calculate_required_date_risk(
            order,
            risk_thresholds=risk_thresholds,
        )

        return result.can_meet_required_date

    # ============================================================
    # 1.3.19 COMBINED ETA RISK VIEW
    # ============================================================

    def calculate_combined_eta_risk(
        self,
        order: ManufacturingOrder,
        *,
        schedule_risk_thresholds: Optional[
            ETARiskThresholds
        ] = None,
        required_date_risk_thresholds: Optional[
            RequiredDateRiskThresholds
        ] = None,
    ) -> tuple[
        ETAScheduleVariance,
        RequiredDateRisk,
    ]:
        """
        Calculate both ETA risk perspectives for the same
        Manufacturing Order.

        Returns:

            (
                internal_schedule_risk,
                required_date_risk,
            )

        Internal schedule risk answers:

            "Are we behind our planned production schedule?"

        Required-date risk answers:

            "Can we meet the required/customer date?"

        This method is read-only.
        """

        schedule_risk = (
            self.calculate_eta_schedule_variance(
                order,
                risk_thresholds=schedule_risk_thresholds,
            )
        )

        required_date_risk = (
            self.calculate_required_date_risk(
                order,
                risk_thresholds=required_date_risk_thresholds,
            )
        )

        return (
            schedule_risk,
            required_date_risk,
        )

    # ============================================================
    # 1.3.21 ETA RISK SUMMARY / DECISION LAYER
    # ============================================================

    def calculate_eta_risk_summary(
        self,
        order: ManufacturingOrder,
        *,
        schedule_risk_thresholds: Optional[
            ETARiskThresholds
        ] = None,
        required_date_risk_thresholds: Optional[
            RequiredDateRiskThresholds
        ] = None,
    ) -> ETARiskSummary:
        """
        Calculate the complete operational ETA risk summary
        for a Manufacturing Order.

        This combines:

            1. Internal production schedule risk
            2. Required/customer-date risk

        into one operational decision.

        The underlying risk calculations remain independent.

        This method is read-only and does not modify the
        Manufacturing Order.
        """

        (
            schedule_risk,
            required_date_risk,
        ) = self.calculate_combined_eta_risk(
            order,
            schedule_risk_thresholds=(
                schedule_risk_thresholds
            ),
            required_date_risk_thresholds=(
                required_date_risk_thresholds
            ),
        )

        calculator = ETARiskSummaryCalculator()

        return calculator.calculate(
            schedule_risk=schedule_risk,
            required_date_risk=required_date_risk,
        )

    # ============================================================
    # 1.3.23 OPERATIONAL ETA SNAPSHOT
    # ============================================================

    def calculate_eta_operational_snapshot(
        self,
        order: ManufacturingOrder,
        *,
        schedule_risk_thresholds: Optional[
            ETARiskThresholds
        ] = None,
        required_date_risk_thresholds: Optional[
            RequiredDateRiskThresholds
        ] = None,
    ) -> ETAOperationalSnapshot:
        """
        Calculate the complete read-only operational ETA
        snapshot for a Manufacturing Order.

        This provides Phoenix Core and future Production UI
        consumers with one clean object containing:

            - planned ETA
            - current/live ETA
            - required date
            - schedule risk
            - required-date risk
            - operational decision
            - action-required flag
            - human-readable summary

        Risk calculation remains delegated to the existing
        ETA risk and ETA risk-summary layers.

        This method does not modify the Manufacturing Order.
        """

        risk_summary = (
            self.calculate_eta_risk_summary(
                order,
                schedule_risk_thresholds=(
                    schedule_risk_thresholds
                ),
                required_date_risk_thresholds=(
                    required_date_risk_thresholds
                ),
            )
        )

        return ETAOperationalSnapshot.from_risk_summary(
            planned_eta=order.eta.planned_eta,
            current_eta=order.eta.current_eta,
            required_date=order.eta.required_date,
            summary=risk_summary,
        )

    # ============================================================
    # 1.3.14 LIVE ETA FROM ROLLING RATE
    # ============================================================

    def calculate_live_eta_from_rolling_rate(
        self,
        order: ManufacturingOrder,
        *,
        window_hours: Decimal,
        calculated_at: Optional[datetime] = None,
        quantity_produced: Optional[Decimal] = None,
    ) -> Optional[ETASnapshot]:
        """
        Calculate Live ETA using recent rolling production rate.
        """

        calculated_at = (
            calculated_at
            or datetime.now(timezone.utc)
        )

        rolling_rate = (
            self.calculate_rolling_production_rate(
                order,
                window_hours=window_hours,
                calculated_at=calculated_at,
                quantity_produced=quantity_produced,
            )
        )

        if rolling_rate is None:
            return None

        if rolling_rate <= Decimal("0"):
            return None

        remaining_quantity = (
            order.quantity.remaining
        )

        if remaining_quantity <= Decimal("0"):
            order.eta.mark_completed(
                calculated_at
            )

            return ETASnapshot(
                calculated_at=calculated_at,
                planned_eta=order.eta.planned_eta,
                current_eta=order.eta.current_eta,
                required_date=order.eta.required_date,
                status=ETAStatus.COMPLETED,
                reason=(
                    "Production quantity is complete"
                ),
            )

        remaining_hours = (
            remaining_quantity
            / rolling_rate
        )

        live_eta = (
            calculated_at
            + timedelta(
                hours=float(
                    remaining_hours
                )
            )
        )

        return order.eta.update_current_eta(
            live_eta,
            calculated_at=calculated_at,
            reason=(
                "Live ETA calculated from rolling "
                "production throughput"
            ),
        )

    # ============================================================
    # 1.3.13 LIVE ETA FROM ACTUAL RATE
    # ============================================================

    def calculate_live_eta_from_actual_rate(
        self,
        order: ManufacturingOrder,
        *,
        calculated_at: Optional[datetime] = None,
    ) -> Optional[ETASnapshot]:
        """
        Calculate Live ETA using the full-history actual rate.
        """

        calculated_at = (
            calculated_at
            or datetime.now(timezone.utc)
        )

        actual_rate = (
            self.calculate_actual_production_rate(
                order,
                calculated_at=calculated_at,
            )
        )

        if actual_rate is None:
            return None

        if actual_rate <= Decimal("0"):
            return None

        remaining_quantity = (
            order.quantity.remaining
        )

        if remaining_quantity <= Decimal("0"):
            order.eta.mark_completed(
                calculated_at
            )

            return ETASnapshot(
                calculated_at=calculated_at,
                planned_eta=order.eta.planned_eta,
                current_eta=order.eta.current_eta,
                required_date=order.eta.required_date,
                status=ETAStatus.COMPLETED,
                reason=(
                    "Production quantity is complete"
                ),
            )

        remaining_hours = (
            remaining_quantity
            / actual_rate
        )

        live_eta = (
            calculated_at
            + timedelta(
                hours=float(
                    remaining_hours
                )
            )
        )

        return order.eta.update_current_eta(
            live_eta,
            calculated_at=calculated_at,
            reason=(
                "Live ETA calculated from actual "
                "production throughput"
            ),
        )

    # ============================================================
    # 1.3.12 AUTOMATIC LIVE ETA
    # ============================================================

    def calculate_live_eta(
        self,
        order: ManufacturingOrder,
        *,
        production_rate_per_hour: Decimal,
        calculated_at: Optional[datetime] = None,
    ) -> Optional[ETASnapshot]:
        """
        Calculate Live ETA using an explicitly supplied rate.
        """

        production_rate_per_hour = Decimal(
            str(production_rate_per_hour)
        )

        if production_rate_per_hour <= Decimal("0"):
            raise ValueError(
                "production_rate_per_hour must be greater than zero"
            )

        if order.eta.actual_production_start is None:
            return None

        calculated_at = (
            calculated_at
            or datetime.now(timezone.utc)
        )

        remaining_quantity = (
            order.quantity.remaining
        )

        if remaining_quantity <= Decimal("0"):
            order.eta.mark_completed(
                calculated_at
            )

            return ETASnapshot(
                calculated_at=calculated_at,
                planned_eta=order.eta.planned_eta,
                current_eta=order.eta.current_eta,
                required_date=order.eta.required_date,
                status=ETAStatus.COMPLETED,
                reason=(
                    "Production quantity is complete"
                ),
            )

        remaining_hours = (
            remaining_quantity
            / production_rate_per_hour
        )

        live_eta = (
            calculated_at
            + timedelta(
                hours=float(
                    remaining_hours
                )
            )
        )

        hold_duration = (
            order.eta.total_hold_duration
        )

        if order.eta.hold_is_active:
            hold_duration += (
                order.eta.current_hold_duration
            )

        live_eta += hold_duration

        return order.eta.update_current_eta(
            live_eta,
            calculated_at=calculated_at,
            reason=(
                "Automatic live ETA calculated from "
                "remaining quantity, production rate "
                "and hold impact"
            ),
        )

    # ============================================================
    # EXISTING LIVE ETA APIs
    # ============================================================

    def calculate_live_eta_from_remaining_work(
        self,
        order: ManufacturingOrder,
        *,
        remaining_production_hours: Decimal,
        calculated_at: Optional[datetime] = None,
    ) -> Optional[ETASnapshot]:
        remaining_production_hours = Decimal(
            str(
                remaining_production_hours
            )
        )

        if remaining_production_hours < 0:
            raise ValueError(
                "remaining_production_hours cannot be negative"
            )

        if order.eta.actual_production_start is None:
            return None

        calculated_at = (
            calculated_at
            or datetime.now(timezone.utc)
        )

        current_eta = (
            calculated_at
            + timedelta(
                hours=float(
                    remaining_production_hours
                )
            )
        )

        return order.eta.update_current_eta(
            current_eta,
            calculated_at=calculated_at,
            reason=(
                "Live ETA calculated from remaining "
                "production workload"
            ),
        )

    def calculate_live_eta_from_rate(
        self,
        order: ManufacturingOrder,
        *,
        remaining_quantity: Decimal,
        production_rate_per_hour: Decimal,
        calculated_at: Optional[datetime] = None,
    ) -> Optional[ETASnapshot]:
        remaining_quantity = Decimal(
            str(
                remaining_quantity
            )
        )

        production_rate_per_hour = Decimal(
            str(
                production_rate_per_hour
            )
        )

        if remaining_quantity < 0:
            raise ValueError(
                "remaining_quantity cannot be negative"
            )

        if production_rate_per_hour <= Decimal("0"):
            raise ValueError(
                "production_rate_per_hour must be greater than zero"
            )

        calculated_at = (
            calculated_at
            or datetime.now(timezone.utc)
        )

        remaining_hours = (
            remaining_quantity
            / production_rate_per_hour
        )

        current_eta = (
            calculated_at
            + timedelta(
                hours=float(
                    remaining_hours
                )
            )
        )

        return order.eta.update_current_eta(
            current_eta,
            calculated_at=calculated_at,
            reason=(
                "Live ETA calculated from remaining "
                "quantity and production rate"
            ),
        )

    # ============================================================
    # ETA STATUS
    # ============================================================

    def mark_material_wait(
        self,
        order: ManufacturingOrder,
    ) -> None:
        order.eta.mark_material_wait()

    def update_current_eta(
        self,
        order: ManufacturingOrder,
        current_eta: Optional[datetime],
        *,
        calculated_at: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> ETASnapshot:
        return order.eta.update_current_eta(
            current_eta,
            calculated_at=calculated_at,
            reason=reason,
        )

    def mark_eta_completed(
        self,
        order: ManufacturingOrder,
        completed_at: datetime,
    ) -> None:
        order.eta.mark_completed(
            completed_at
        )

    def get_eta_status(
        self,
        order: ManufacturingOrder,
    ) -> ETAStatus:
        return order.eta.status