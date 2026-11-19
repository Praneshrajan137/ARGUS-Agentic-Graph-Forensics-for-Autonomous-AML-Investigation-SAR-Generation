"""Versioned detection policy and institution business-day configuration.

Research presets are explicitly marked as synthetic baselines and never represent
statutory filing thresholds or institution-approved operational policy.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class CurrencyStructuringThreshold:
    currency: str
    min_amount: Decimal
    max_amount: Decimal
    min_count: int
    window_seconds: int


@dataclass(frozen=True)
class BusinessDayConfig:
    mode: Literal["ROLLING_SECONDS", "INSTITUTION_BUSINESS_DAY"] = "ROLLING_SECONDS"
    institution_timezone: str = "America/New_York"
    cutoff_hour: int = 17
    business_days_window: int = 2
    holidays: tuple[str, ...] = ()  # ISO YYYY-MM-DD dates in institution timezone

    def business_day_key(self, event_at: datetime) -> str:
        """Map an aware timestamp to its institution business date (YYYY-MM-DD)."""
        tz = ZoneInfo(self.institution_timezone)
        local_dt = event_at.astimezone(tz)
        day = local_dt.date()
        if local_dt.hour >= self.cutoff_hour:
            day = day + timedelta(days=1)
        holiday_set = set(self.holidays)
        while day.weekday() >= 5 or day.isoformat() in holiday_set:
            day = day + timedelta(days=1)
        return day.isoformat()

    def business_day_index(self, event_at: datetime) -> int:
        """Return monotonic business-day ordinal for exact business-day windowing."""
        key = self.business_day_key(event_at)
        target = datetime.fromisoformat(key).date()
        # Reference anchor 2000-01-03 (Monday)
        anchor = datetime(2000, 1, 3, tzinfo=timezone.utc).date()
        delta_days = (target - anchor).days
        # Count weekday business days minus holidays between anchor and target
        full_weeks, rem = divmod(delta_days, 7)
        count = full_weeks * 5 + min(rem, 5)
        holiday_count = sum(
            1 for h in self.holidays
            if anchor <= datetime.fromisoformat(h).date() <= target
            and datetime.fromisoformat(h).date().weekday() < 5
        )
        return count - holiday_count


@dataclass(frozen=True)
class RulePolicy:
    policy_id: str
    policy_version: str
    rationale: str
    is_synthetic_preset: bool
    structuring_thresholds: dict[str, CurrencyStructuringThreshold] = field(default_factory=dict)
    layering_min_hops: int = 3
    layering_max_depth: int = 5
    layering_decay_min: Decimal = Decimal("0.02")
    layering_decay_max: Decimal = Decimal("0.05")
    layering_decay_tolerance: Decimal = Decimal("0.005")
    layering_max_hop_delay_seconds: int = 43_200
    business_day: BusinessDayConfig = field(default_factory=BusinessDayConfig)

    def threshold_for(self, currency: str) -> CurrencyStructuringThreshold | None:
        """Return explicit threshold for currency, or None if unsupported (never defaults to USD)."""
        return self.structuring_thresholds.get(currency)

    def to_metadata(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "rationale": self.rationale,
            "is_synthetic_preset": self.is_synthetic_preset,
            "supported_currencies": sorted(self.structuring_thresholds.keys()),
            "window_mode": self.business_day.mode,
            "institution_timezone": self.business_day.institution_timezone,
            "business_day_cutoff_hour": self.business_day.cutoff_hour,
            "business_days_window": self.business_day.business_days_window,
            "layering": {
                "min_hops": self.layering_min_hops,
                "max_depth": self.layering_max_depth,
                "decay_min": str(self.layering_decay_min),
                "decay_max": str(self.layering_decay_max),
                "decay_tolerance": str(self.layering_decay_tolerance),
                "max_hop_delay_seconds": self.layering_max_hop_delay_seconds,
            },
        }


DEFAULT_PRODUCTION_POLICY = RulePolicy(
    policy_id="argus-us-synthetic-baseline",
    policy_version="2026.11-baseline",
    rationale=(
        "Unvalidated synthetic baseline configuration for local testing and evaluation. "
        "Requires institution-approved thresholds, product scoping, and business-day calendar before live use."
    ),
    is_synthetic_preset=True,
    structuring_thresholds={
        "USD": CurrencyStructuringThreshold(
            currency="USD",
            min_amount=Decimal("9000"),
            max_amount=Decimal("9800"),
            min_count=10,
            window_seconds=172_800,
        ),
        "INR": CurrencyStructuringThreshold(
            currency="INR",
            min_amount=Decimal("900000"),
            max_amount=Decimal("980000"),
            min_count=10,
            window_seconds=172_800,
        ),
    },
)
