"""Transport-independent observations, intents and bounded recovery state."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import math
from typing import Any, Optional


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


@dataclass(frozen=True)
class Telemetry:
    at: float
    status: frozenset[str]
    charge: Optional[float]
    runtime: Optional[float]
    source_age_seconds: float = 0

    @classmethod
    def from_variables(cls, variables: dict[str, str], at: float,
                       source_age_seconds: float = 0) -> Telemetry:
        if _number(at) is None or _number(source_age_seconds) is None:
            raise ValueError("Invalid observation time/age")
        raw_status = variables.get("ups.status", "")
        status = frozenset(raw_status.split()) if isinstance(raw_status, str) else frozenset()
        # Contradictory mains state must not satisfy either recovery or outage.
        if "OL" in status and "OB" in status:
            status = frozenset()
        charge = _number(variables.get("battery.charge"))
        if charge is not None and charge > 100:
            charge = None
        return cls(float(at), status, charge, _number(variables.get("battery.runtime")),
                   float(source_age_seconds))

    @property
    def online(self) -> bool:
        return "OL" in self.status and not self.status.intersection({"OB", "OFF", "FSD", "OVER", "ALARM", "LB"})

    @property
    def on_battery(self) -> bool:
        return "OB" in self.status


@dataclass(frozen=True)
class HostFacts:
    """Explicit simulator observations, never inferred from a planned action."""
    awake: Optional[bool] = None
    ready: bool = False
    shutdown_confirmed: bool = False
    boot_id: Optional[str] = None


@dataclass(frozen=True)
class Action:
    kind: str
    target: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class State:
    version: int = 1
    incident: int = 0
    outage_since: Optional[float] = None
    stage: int = 0
    online_since: Optional[float] = None
    unknown_since: Optional[float] = None
    last_at: Optional[float] = None
    clock_uncertain: bool = False
    seen_online: bool = False
    maintenance_since: Optional[float] = None
    maintenance_hours: int = 0
    recovery_targets: list[str] = field(default_factory=list)
    shutdown_planned: list[str] = field(default_factory=list)
    awake_before: list[str] = field(default_factory=list)
    off_before: list[str] = field(default_factory=list)
    affected: list[str] = field(default_factory=list)
    host_boot_ids: dict[str, str] = field(default_factory=dict)
    host_awake: dict[str, Optional[bool]] = field(default_factory=dict)
    emitted: dict[str, str] = field(default_factory=dict)
    wake_attempts: dict[str, int] = field(default_factory=dict)
    wake_last_at: dict[str, float] = field(default_factory=dict)
    wake_started_at: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> State:
        expected = {f.name for f in fields(cls)}
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("Invalid checkpoint fields")
        for key in ("version", "incident", "stage", "maintenance_hours"):
            if type(value[key]) is not int or value[key] < 0:
                raise ValueError("Invalid checkpoint counters")
        if value["version"] != 1 or value["stage"] not in (0, 1, 2, 3):
            raise ValueError("Unsupported checkpoint version/stage")
        for key in ("outage_since", "online_since", "unknown_since", "last_at", "maintenance_since"):
            if value[key] is not None and (type(value[key]) not in (int, float) or _number(value[key]) is None):
                raise ValueError("Invalid checkpoint timestamp")
        for key in ("clock_uncertain", "seen_online"):
            if type(value[key]) is not bool:
                raise ValueError("Invalid checkpoint flags")
        for key in ("recovery_targets", "shutdown_planned", "awake_before", "off_before", "affected"):
            items = value[key]
            if not isinstance(items, list) or not all(isinstance(x, str) for x in items) or len(items) != len(set(items)):
                raise ValueError("Invalid checkpoint host list")
        for key in ("emitted", "wake_attempts", "wake_last_at", "wake_started_at", "host_boot_ids", "host_awake"):
            items = value[key]
            if not isinstance(items, dict) or not all(isinstance(k, str) for k in items):
                raise ValueError("Invalid checkpoint map")
            for item in items.values():
                if key in ("emitted", "host_boot_ids") and not isinstance(item, str):
                    raise ValueError("Invalid checkpoint action marker")
                if key == "wake_attempts" and (type(item) is not int or item < 0):
                    raise ValueError("Invalid wake counter")
                if key in ("wake_last_at", "wake_started_at") and (type(item) not in (int, float) or _number(item) is None):
                    raise ValueError("Invalid wake timestamp")
                if key == "host_awake" and item is not None and type(item) is not bool:
                    raise ValueError("Invalid awake checkpoint")
        return cls(**value)
