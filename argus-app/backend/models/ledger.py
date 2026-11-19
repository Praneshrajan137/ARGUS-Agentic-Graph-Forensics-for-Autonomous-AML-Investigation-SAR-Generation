import re
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecordKind(StrEnum):
    ENTITIES = "entities"
    ACCOUNTS = "accounts"
    RELATIONSHIPS = "relationships"
    TRANSACTIONS = "transactions"


REQUIRED_HEADERS = {
    "entities": ("id", "entity_type", "name"),
    "accounts": ("id", "account_type", "currency"),
    "relationships": ("id", "entity_id", "account_id", "role", "valid_from", "valid_to"),
    "transactions": ("id", "event_type", "source_account_id", "target_account_id", "amount", "currency", "event_at", "posted_at", "related_event_id"),
}


def decimal_string(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def money(text: str) -> Decimal:
    if not isinstance(text, str) or len(text) > 64 or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,10})?", text):
        raise ValueError("Amount must be a plain decimal with at most ten fractional digits")
    if len(text.replace(".", "").lstrip("0")) > 30:
        raise ValueError("Amount exceeds thirty digits")
    value = Decimal(text)
    if not value.is_finite() or value <= 0:
        raise ValueError("Amount must be finite and positive")
    return value


def timestamp(text: str) -> datetime:
    if not isinstance(text, str) or "T" not in text:
        raise ValueError("Timestamp must include time and timezone")
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include timezone")
    return value.astimezone(timezone.utc)


class RecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=128)
    supersedes_hash: str | None = None

    @field_validator("id")
    @classmethod
    def identity(cls, value: str) -> str:
        if value != value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("Identifier has whitespace or control characters")
        return value

    @field_validator("supersedes_hash", mode="before")
    @classmethod
    def revision(cls, value):
        if value in (None, ""):
            return None
        if not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("Correction requires an exact previous record digest")
        return value


class EntityInput(RecordInput):
    entity_type: Literal["PERSON", "BUSINESS", "OTHER", "UNKNOWN"]
    name: str = Field(min_length=1, max_length=512)
    country: str | None = None


class AccountInput(RecordInput):
    account_type: Literal["CHECKING", "SAVINGS", "CASH", "OTHER", "UNKNOWN"]
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class RelationshipInput(RecordInput):
    entity_id: str = Field(min_length=1, max_length=128)
    account_id: str = Field(min_length=1, max_length=128)
    role: Literal["OWNER", "SIGNATORY", "BENEFICIARY"]
    valid_from: str
    valid_to: str | None = None

    @model_validator(mode="after")
    def interval(self):
        start = timestamp(self.valid_from)
        if self.valid_to and timestamp(self.valid_to) <= start:
            raise ValueError("Relationship end must follow start")
        self.valid_to = self.valid_to or None
        return self


SCHEMA_VERSION = "canonical-csv-v1"
TRANSFORMATION_VERSION = "argus-intake-v1"


def analysis_eligibility(payload: dict) -> tuple[bool, str | None]:
    """Classify whether a normalized transaction is eligible for detection analysis."""
    status = payload.get("status", "POSTED")
    if status == "PENDING":
        return False, "PENDING_EVENT"
    if status == "CANCELLED":
        return False, "CANCELLED_EVENT"
    event_type = payload.get("event_type")
    if event_type == "FX_CONVERSION":
        return False, "FX_EVENT_UNSUPPORTED"
    if event_type == "UNSUPPORTED":
        return False, "UNSUPPORTED_EVENT_TYPE"
    if event_type == "REVERSAL":
        return False, "REVERSAL_EVENT"
    return True, None


class TransactionInput(RecordInput):
    event_type: Literal["TRANSFER", "CASH_DEPOSIT", "CASH_WITHDRAWAL", "REVERSAL", "FX_CONVERSION", "UNSUPPORTED"]
    source_account_id: str | None = Field(default=None, max_length=128)
    target_account_id: str | None = Field(default=None, max_length=128)
    amount: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    event_at: str
    posted_at: str
    related_event_id: str | None = Field(default=None, max_length=128)
    status: Literal["POSTED", "PENDING", "CANCELLED"] = "POSTED"
    posting_group_id: str | None = Field(default=None, max_length=128)
    posting_leg: Literal["DEBIT", "CREDIT"] | None = None
    fx_counter_currency: str | None = None
    fx_rate: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_value(cls, value: str) -> str:
        return decimal_string(money(value))

    @field_validator("event_at", "posted_at")
    @classmethod
    def event_time(cls, value: str) -> str:
        return timestamp(value).isoformat()

    @field_validator("source_account_id", "target_account_id", "related_event_id", "posting_group_id", mode="before")
    @classmethod
    def nullable_id(cls, value):
        if value in (None, ""):
            return None
        return cls.identity(value)

    @field_validator("status", mode="before")
    @classmethod
    def default_status(cls, value):
        if value in (None, ""):
            return "POSTED"
        return value

    @field_validator("posting_leg", mode="before")
    @classmethod
    def nullable_leg(cls, value):
        if value in (None, ""):
            return None
        return value

    @field_validator("fx_counter_currency", mode="before")
    @classmethod
    def nullable_fx_currency(cls, value):
        if value in (None, ""):
            return None
        if not isinstance(value, str) or not re.fullmatch(r"^[A-Z]{3}$", value):
            raise ValueError("FX counter currency must be a 3-letter ISO code")
        return value

    @field_validator("fx_rate", mode="before")
    @classmethod
    def nullable_fx_rate(cls, value):
        if value in (None, ""):
            return None
        return decimal_string(money(value))

    @model_validator(mode="after")
    def endpoints(self):
        if self.event_type == "CASH_DEPOSIT":
            valid = self.target_account_id and not self.source_account_id
        elif self.event_type == "CASH_WITHDRAWAL":
            valid = self.source_account_id and not self.target_account_id
        elif self.event_type in ("FX_CONVERSION", "UNSUPPORTED"):
            valid = bool(self.source_account_id or self.target_account_id)
        else:
            valid = bool(self.source_account_id and self.target_account_id)
        if not valid:
            raise ValueError("Event endpoints do not match the declared economic event type")
        if self.event_type == "REVERSAL" and not self.related_event_id:
            raise ValueError("Reversal requires related_event_id")
        if self.event_type != "REVERSAL" and self.related_event_id:
            raise ValueError("Only reversals can declare related_event_id")
        if bool(self.posting_group_id) != bool(self.posting_leg):
            raise ValueError("posting_group_id and posting_leg must be supplied together")
        return self


INPUT_MODELS = {
    "entities": EntityInput,
    "accounts": AccountInput,
    "relationships": RelationshipInput,
    "transactions": TransactionInput,
}
