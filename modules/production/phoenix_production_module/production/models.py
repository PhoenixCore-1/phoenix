from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


ZERO = Decimal("0")


class ProductionState(str, Enum):
    PLANNED = "PLANNED"
    RELEASED = "RELEASED"
    STARTED = "STARTED"
    HOLD = "HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ETAStatus(str, Enum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    LATE = "LATE"
    MATERIAL_WAIT = "MATERIAL_WAIT"
    NOT_STARTED = "NOT_STARTED"
    COMPLETED = "COMPLETED"
    UNKNOWN = "UNKNOWN"


@dataclass
class QuantityLedger:
    """
    Order-level production quantity ledger.

    Stage quantities must not be added together to determine total
    production quantity because the same physical quantity can move
    through multiple manufacturing stages.
    """

    planned: Decimal
    accepted: Decimal = ZERO
    rejected: Decimal = ZERO
    rework: Decimal = ZERO

    def __post_init__(self) -> None:
        self.planned = Decimal(str(self.planned))
        self.accepted = Decimal(str(self.accepted))
        self.rejected = Decimal(str(self.rejected))
        self.rework = Decimal(str(self.rework))

    @property
    def processed(self) -> Decimal:
        return (
            self.accepted
            + self.rejected
            + self.rework
        )

    @property
    def remaining(self) -> Decimal:
        value = self.planned - self.processed
        return max(value, ZERO)


@dataclass
class StageQuantityLedger:
    """
    Stage-level quantity accounting.

    WIP = Input - Accepted - Rejected

    Rework is a classification of WIP and is therefore NOT added
    again to the WIP total.
    """

    input_quantity: Decimal
    accepted: Decimal = ZERO
    rejected: Decimal = ZERO
    rework: Decimal = ZERO

    def __post_init__(self) -> None:
        self.input_quantity = Decimal(str(self.input_quantity))
        self.accepted = Decimal(str(self.accepted))
        self.rejected = Decimal(str(self.rejected))
        self.rework = Decimal(str(self.rework))
        self._validate()

    def _validate(self) -> None:
        if self.input_quantity < ZERO:
            raise ValueError(
                "input_quantity cannot be negative"
            )

        if self.accepted < ZERO:
            raise ValueError(
                "accepted quantity cannot be negative"
            )

        if self.rejected < ZERO:
            raise ValueError(
                "rejected quantity cannot be negative"
            )

        if self.rework < ZERO:
            raise ValueError(
                "rework quantity cannot be negative"
            )

        if (
            self.accepted + self.rejected
            > self.input_quantity
        ):
            raise ValueError(
                "Accepted and rejected quantity cannot exceed "
                "stage input"
            )

        if self.rework > self.wip:
            raise ValueError(
                "Rework quantity cannot exceed stage WIP"
            )

    @property
    def output_quantity(self) -> Decimal:
        return self.accepted + self.rejected

    @property
    def wip(self) -> Decimal:
        return max(
            self.input_quantity
            - self.accepted
            - self.rejected,
            ZERO,
        )

    @property
    def remaining(self) -> Decimal:
        return self.wip

    @property
    def available_to_next_stage(self) -> Decimal:
        return self.accepted

    @property
    def is_complete(self) -> bool:
        return self.wip == ZERO

    def record(
        self,
        *,
        accepted: Decimal = ZERO,
        rejected: Decimal = ZERO,
        rework: Decimal = ZERO,
    ) -> None:
        accepted = Decimal(str(accepted))
        rejected = Decimal(str(rejected))
        rework = Decimal(str(rework))

        if accepted < ZERO:
            raise ValueError(
                "accepted quantity cannot be negative"
            )

        if rejected < ZERO:
            raise ValueError(
                "rejected quantity cannot be negative"
            )

        if rework < ZERO:
            raise ValueError(
                "rework quantity cannot be negative"
            )

        new_accepted = self.accepted + accepted
        new_rejected = self.rejected + rejected
        new_rework = self.rework + rework

        if (
            new_accepted + new_rejected
            > self.input_quantity
        ):
            raise ValueError(
                "Recorded output cannot exceed stage input"
            )

        new_wip = (
            self.input_quantity
            - new_accepted
            - new_rejected
        )

        if new_rework > new_wip:
            raise ValueError(
                "Rework quantity cannot exceed stage WIP"
            )

        self.accepted = new_accepted
        self.rejected = new_rejected
        self.rework = new_rework


@dataclass
class StageReconciliation:
    """
    Reconciles physical quantity available from the previous stage
    against quantity entering the current stage.
    """

    previous_stage: StageQuantityLedger
    current_stage: StageQuantityLedger

    def __post_init__(self) -> None:
        if (
            self.current_stage.input_quantity
            > self.previous_stage.available_to_next_stage
        ):
            raise ValueError(
                "Current stage input cannot exceed "
                "previous stage accepted quantity"
            )

    @property
    def available_input(self) -> Decimal:
        return self.previous_stage.available_to_next_stage

    @property
    def current_stage_input(self) -> Decimal:
        return self.current_stage.input_quantity

    @property
    def input_variance(self) -> Decimal:
        return (
            self.available_input
            - self.current_stage_input
        )

    @property
    def is_reconciled(self) -> bool:
        return self.input_variance >= ZERO

    def validate(self) -> bool:
        if not self.is_reconciled:
            raise ValueError(
                "Stage quantity reconciliation failed"
            )

        return True


def validate_stage_input(
    *,
    previous_stage: StageQuantityLedger,
    current_stage_input: Decimal,
) -> Decimal:
    """
    Validate that the next stage does not receive more quantity
    than the previous stage successfully accepted.
    """

    current_stage_input = Decimal(
        str(current_stage_input)
    )

    if current_stage_input < ZERO:
        raise ValueError(
            "current_stage_input cannot be negative"
        )

    available_input = (
        previous_stage.available_to_next_stage
    )

    if current_stage_input > available_input:
        raise ValueError(
            "Current stage input cannot exceed "
            "previous stage accepted quantity"
        )

    return current_stage_input


@dataclass
class MaterialRequirement:
    """
    Generic material requirement used by the ETA foundation.
    """

    material_id: str
    required_quantity: Decimal
    supplier_lead_time_days: Decimal
    order_date: Optional[datetime] = None
    expected_arrival: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.required_quantity = Decimal(
            str(self.required_quantity)
        )

        self.supplier_lead_time_days = Decimal(
            str(self.supplier_lead_time_days)
        )

        if not self.material_id.strip():
            raise ValueError(
                "material_id is required"
            )

        if self.required_quantity <= ZERO:
            raise ValueError(
                "required_quantity must be greater than zero"
            )

        if self.supplier_lead_time_days < ZERO:
            raise ValueError(
                "supplier_lead_time_days cannot be negative"
            )

        if (
            self.order_date is not None
            and self.expected_arrival is None
        ):
            self.expected_arrival = (
                self.calculate_expected_arrival()
            )

    def calculate_expected_arrival(
        self,
    ) -> Optional[datetime]:
        if self.order_date is None:
            return None

        return (
            self.order_date
            + timedelta(
                days=float(
                    self.supplier_lead_time_days
                )
            )
        )

    @property
    def is_ordered(self) -> bool:
        return self.order_date is not None

    @property
    def is_received(self) -> bool:
        return self.actual_arrival is not None

    @property
    def is_available(self) -> bool:
        return self.actual_arrival is not None


@dataclass
class ETASnapshot:
    """
    Represents one calculated ETA point.
    """

    calculated_at: datetime
    planned_eta: Optional[datetime]
    current_eta: Optional[datetime]
    required_date: Optional[datetime]
    status: ETAStatus
    reason: Optional[str] = None

    @property
    def is_late(self) -> bool:
        if self.current_eta is None:
            return False

        if self.required_date is None:
            return False

        return self.current_eta > self.required_date


@dataclass
class ETAPlan:
    """
    ETA foundation for a Manufacturing Order.

    Lifecycle:

        Material readiness
            ->
        Planned production start
            ->
        Actual production start
            ->
        Planned ETA
            ->
        Current/live ETA
            ->
        Actual completion

    Hold handling:

        Production starts
            ->
        Hold begins
            ->
        Hold ends
            ->
        Hold duration accumulated
            ->
        Live ETA can be extended by the accumulated hold time
    """

    required_date: Optional[datetime] = None

    material_ready_date: Optional[datetime] = None

    planned_production_start: Optional[datetime] = None
    actual_production_start: Optional[datetime] = None

    planned_eta: Optional[datetime] = None
    current_eta: Optional[datetime] = None

    actual_completion: Optional[datetime] = None

    status: ETAStatus = ETAStatus.UNKNOWN

    last_calculated_at: Optional[datetime] = None

    # ------------------------------------------------------------
    # HOLD TRACKING
    # ------------------------------------------------------------

    hold_started_at: Optional[datetime] = None
    last_hold_resumed_at: Optional[datetime] = None
    total_hold_duration: timedelta = field(
        default_factory=timedelta
    )

    def calculate_material_ready_date(
        self,
        materials: list[MaterialRequirement],
    ) -> Optional[datetime]:
        """
        The latest required material arrival determines readiness.
        """

        if not materials:
            self.material_ready_date = None
            return None

        dates: list[datetime] = []

        for material in materials:
            if material.actual_arrival is not None:
                dates.append(
                    material.actual_arrival
                )
                continue

            if material.expected_arrival is not None:
                dates.append(
                    material.expected_arrival
                )
                continue

            self.material_ready_date = None
            return None

        self.material_ready_date = max(dates)

        return self.material_ready_date

    def establish_planned_eta(
        self,
        *,
        planned_production_start: Optional[datetime],
        planned_eta: Optional[datetime],
    ) -> None:
        self.planned_production_start = (
            planned_production_start
        )

        self.planned_eta = planned_eta

        if self.current_eta is None:
            self.current_eta = planned_eta

    def mark_production_started(
        self,
        started_at: datetime,
    ) -> None:
        self.actual_production_start = started_at

        if self.status == ETAStatus.MATERIAL_WAIT:
            self.status = ETAStatus.NOT_STARTED

    # ------------------------------------------------------------
    # HOLD ACCOUNTING
    # ------------------------------------------------------------

    def mark_hold_started(
        self,
        hold_started_at: datetime,
    ) -> None:
        """
        Begin a production hold period.

        A second hold cannot begin while another hold is already
        active.
        """

        if self.hold_started_at is not None:
            raise ValueError(
                "A production hold is already active"
            )

        self.hold_started_at = hold_started_at

    def mark_hold_resumed(
        self,
        resumed_at: datetime,
    ) -> timedelta:
        """
        End the current hold and add its duration to the
        accumulated hold time.

        Returns the duration of the hold that just ended.
        """

        if self.hold_started_at is None:
            raise ValueError(
                "No active production hold exists"
            )

        if resumed_at < self.hold_started_at:
            raise ValueError(
                "Hold resume time cannot be before hold start time"
            )

        duration = (
            resumed_at
            - self.hold_started_at
        )

        self.total_hold_duration += duration

        self.last_hold_resumed_at = resumed_at
        self.hold_started_at = None

        return duration

    @property
    def hold_is_active(self) -> bool:
        return self.hold_started_at is not None

    @property
    def current_hold_duration(
        self,
    ) -> timedelta:
        """
        Return the duration of the currently active hold.

        Returns zero when no hold is active.
        """

        if self.hold_started_at is None:
            return timedelta(0)

        now = datetime.now(
            tz=self.hold_started_at.tzinfo
        )

        if now < self.hold_started_at:
            return timedelta(0)

        return now - self.hold_started_at

    @property
    def effective_hold_duration(
        self,
    ) -> timedelta:
        """
        Total accumulated hold time plus the current active hold,
        if any.
        """

        return (
            self.total_hold_duration
            + self.current_hold_duration
        )

    def calculate_hold_adjusted_eta(
        self,
        base_eta: datetime,
    ) -> datetime:
        """
        Extend a base ETA by accumulated production hold time.

        The calculation does not modify current_eta. It returns the
        adjusted ETA so the service layer can decide when to commit
        the new live ETA.
        """

        return (
            base_eta
            + self.effective_hold_duration
        )

    # ------------------------------------------------------------
    # LIVE ETA
    # ------------------------------------------------------------

    def update_current_eta(
        self,
        current_eta: Optional[datetime],
        *,
        calculated_at: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> ETASnapshot:
        calculated_at = (
            calculated_at
            or datetime.now()
        )

        self.current_eta = current_eta
        self.last_calculated_at = calculated_at

        if self.actual_completion is not None:
            self.status = ETAStatus.COMPLETED

        elif current_eta is None:
            self.status = ETAStatus.UNKNOWN

        elif (
            self.required_date is not None
            and current_eta > self.required_date
        ):
            self.status = ETAStatus.LATE

        else:
            self.status = ETAStatus.ON_TRACK

        return ETASnapshot(
            calculated_at=calculated_at,
            planned_eta=self.planned_eta,
            current_eta=self.current_eta,
            required_date=self.required_date,
            status=self.status,
            reason=reason,
        )

    def mark_material_wait(self) -> None:
        self.status = ETAStatus.MATERIAL_WAIT

    def mark_completed(
        self,
        completed_at: datetime,
    ) -> None:
        """
        Complete ETA tracking.

        If a hold is somehow still active, it is closed at the
        completion timestamp so the hold duration remains accurate.
        """

        if self.hold_started_at is not None:
            self.mark_hold_resumed(
                completed_at
            )

        self.actual_completion = completed_at

        # Once manufacturing is complete, the final/current ETA is
        # the actual completion timestamp. This ensures the completed
        # ETA represents when production actually finished rather than
        # retaining a previous forecast or remaining unset.
        self.current_eta = completed_at

        self.last_calculated_at = completed_at
        self.status = ETAStatus.COMPLETED


@dataclass
class ManufacturingStage:
    """
    Domain representation of a manufacturing stage.
    """

    stage_id: Optional[int]
    stage_code: str
    stage_name: str
    sequence: int
    quantity: StageQuantityLedger
    status: str = "Ready"
    location: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.stage_code.strip():
            raise ValueError(
                "stage_code is required"
            )

        if not self.stage_name.strip():
            raise ValueError(
                "stage_name is required"
            )

        if self.sequence <= 0:
            raise ValueError(
                "stage sequence must be greater than zero"
            )


@dataclass
class ManufacturingOrder:
    tenant_id: str
    site_id: str
    product_id: str
    planned_quantity: Decimal
    required_date: datetime

    mo_id: UUID = field(
        default_factory=uuid4
    )

    state: ProductionState = (
        ProductionState.PLANNED
    )

    quantity: QuantityLedger = field(
        init=False
    )

    hold_reason: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    eta: ETAPlan = field(
        init=False
    )

    _material_requirements: list[
        MaterialRequirement
    ] = field(
        default_factory=list,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self.planned_quantity = Decimal(
            str(self.planned_quantity)
        )

        if self.planned_quantity <= ZERO:
            raise ValueError(
                "planned_quantity must be greater than zero"
            )

        self.quantity = QuantityLedger(
            planned=self.planned_quantity
        )

        self.eta = ETAPlan(
            required_date=self.required_date
        )

    def add_material_requirement(
        self,
        material: MaterialRequirement,
    ) -> None:
        if not isinstance(
            material,
            MaterialRequirement,
        ):
            raise TypeError(
                "material must be a MaterialRequirement"
            )

        self._material_requirements.append(
            material
        )

    @property
    def material_requirements(
        self,
    ) -> tuple[
        MaterialRequirement,
        ...
    ]:
        return tuple(
            self._material_requirements
        )

    def calculate_material_ready_date(
        self,
    ) -> Optional[datetime]:
        return self.eta.calculate_material_ready_date(
            list(
                self.material_requirements
            )
        )