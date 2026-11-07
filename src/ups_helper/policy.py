"""Pure outage planner. An intent is never evidence that equipment changed."""
from __future__ import annotations

from dataclasses import asdict
import json
from typing import Optional

from .config import Config
from .model import Action, HostFacts, State, Telemetry


MAINTENANCE_ATTEMPT_SECONDS = 15


class Engine:
    def __init__(self, config: Config, state: Optional[State] = None):
        if config.mode != "observe":
            raise ValueError("Only observe mode is implemented")
        self.config = config
        self.state = state if state is not None else State()
        # Stable-mains qualification must be observed continuously by this
        # process, never reconstructed from a downtime gap in a checkpoint.
        self.state.online_since = None
        self.state.seen_online = False
        self._hosts = {h.name: h for h in config.hosts if h.enabled}
        for name in self._hosts:
            if name == config.service.controller_id:
                raise ValueError("The controller cannot be a managed host")
        # Forget removed inventory targets rather than waking stale devices.
        for key in ("recovery_targets", "shutdown_planned", "awake_before", "off_before", "affected"):
            setattr(self.state, key, [n for n in getattr(self.state, key) if n in self._hosts])
        for key in ("wake_attempts", "wake_last_at", "wake_started_at", "host_boot_ids", "host_awake"):
            setattr(self.state, key, {n: v for n, v in getattr(self.state, key).items() if n in self._hosts})
        allowed = set(self._hosts) | {config.service.controller_id}
        self.state.emitted = {k: v for k, v in self.state.emitted.items() if k.partition(":")[2] in allowed}
        # A pre-reboot wall timestamp must not stall required wake retries.
        self.state.wake_last_at.clear()
        self.state.wake_started_at.clear()

    def _emit(self, actions: list[Action], kind: str, target: str, reason: str,
              **details) -> None:
        if target not in self._hosts and target != self.config.service.controller_id:
            raise ValueError("Unknown action target")
        if kind == "shutdown" and target == self.config.service.controller_id:
            raise ValueError("The Pi must never be shut down")
        marker = json.dumps([self.state.incident, details], sort_keys=True)
        key = kind + ":" + target
        if self.state.emitted.get(key) != marker:
            self.state.emitted[key] = marker
            actions.append(Action(kind, target, reason, details))

    def _shutdown(self, actions: list[Action], reason: str) -> None:
        self.state.stage = 3
        for name in self.state.affected:
            if name not in self.state.shutdown_planned:
                self.state.shutdown_planned.append(name)
            self._emit(actions, "shutdown", name, reason)

    def step(self, sample: Telemetry, hosts: Optional[dict[str, HostFacts]] = None,
             maintenance: Optional[dict[str, bool]] = None) -> list[Action]:
        hosts, maintenance = hosts or {}, maintenance or {}
        s, p, now = self.state, self.config.policy, sample.at
        actions: list[Action] = []
        if s.last_at is not None and now < s.last_at:
            s.clock_uncertain = True
            s.online_since = None
            self._emit(actions, "alert", self.config.service.controller_id, "clock moved backwards")
        s.last_at = now
        for name, fact in hosts.items():
            if name not in self._hosts:
                raise ValueError("Unknown host observation")
            restarted = fact.boot_id is not None and fact.boot_id != s.host_boot_ids.get(name, fact.boot_id)
            newly_awake = fact.awake is True and s.host_awake.get(name) is not True
            if restarted or newly_awake:
                for kind in ("shutdown", "power_light", "power_drastic", "restore_power", "check_readiness"):
                    s.emitted.pop(kind + ":" + name, None)
            if fact.boot_id is not None:
                s.host_boot_ids[name] = fact.boot_id
            if fact.awake is not None:
                s.host_awake[name] = fact.awake
            if s.outage_since is None:
                if fact.awake is True:
                    if name not in s.awake_before:
                        s.awake_before.append(name)
                    if name in s.off_before:
                        s.off_before.remove(name)
                elif fact.awake is False:
                    if name in s.awake_before:
                        s.awake_before.remove(name)
                    if name not in s.off_before:
                        s.off_before.append(name)
            if fact.shutdown_confirmed and s.outage_since is not None and name in s.affected:
                if name not in s.recovery_targets:
                    s.recovery_targets.append(name)
        valid_energy = sample.charge is not None and sample.runtime is not None
        valid_age = sample.source_age_seconds <= self.config.nut.max_source_age_seconds
        known = valid_age and (sample.online or (sample.on_battery and valid_energy))
        if not known:
            s.online_since = None
            if s.unknown_since is None:
                s.unknown_since = now
            self._emit(actions, "alert", self.config.service.controller_id, "UPS state or required energy data unavailable")
            if now - s.unknown_since >= p.unknown_shutdown_seconds and s.outage_since is not None:
                self._shutdown(actions, "UPS data unavailable during a known incident")
        else:
            s.unknown_since = None

        # Even a missing runtime/charge field must not mask a fresh emergency.
        remaining = None if sample.runtime is None else max(
            0, sample.runtime - sample.source_age_seconds - p.runtime_uncertainty_seconds)
        emergency = "FSD" in sample.status or bool(sample.status.intersection({"OVER", "OFF"})) or (
            sample.on_battery and (
                "LB" in sample.status or
                (sample.charge is not None and sample.charge <= p.critical_charge_percent) or
                (remaining is not None and remaining <= p.runtime_reserve_seconds)))
        if sample.on_battery or emergency:
            s.online_since = None
            if s.outage_since is None:
                s.incident += 1
                s.outage_since = now
                s.affected = [n for n in self._hosts if n not in s.off_before]
                if s.unknown_since is not None:
                    s.unknown_since = now
                s.emitted.clear()
                # Boot on battery with no trustworthy incident history must
                # not manufacture a new full grace period.
                if not s.seen_online:
                    s.clock_uncertain = True
            elapsed = now - s.outage_since
            if emergency or s.clock_uncertain or s.stage == 3:
                self._shutdown(actions, "critical energy, supply fault or uncertain outage age")
            elif elapsed >= p.shutdown_after_seconds:
                self._shutdown(actions, "maximum outage duration reached")
            elif known and s.stage < 3:
                if elapsed >= p.grace_seconds:
                    s.stage = max(s.stage, 1)
                    for name in s.affected:
                        host = self._hosts[name]
                        self._emit(actions, "power_light", name, "outage grace expired",
                                   profile=asdict(host.light))
                    if (elapsed >= p.drastic_after_seconds or
                            sample.charge <= p.drastic_charge_percent or
                            remaining <= p.runtime_reserve_seconds + p.drastic_runtime_margin_seconds):
                        s.stage = 2
                        for name in s.affected:
                            host = self._hosts[name]
                            self._emit(actions, "power_drastic", name, "outage persisted or reserve tightening",
                                       profile=asdict(host.drastic))
                        if s.maintenance_since is None:
                            s.maintenance_since = now
                            s.maintenance_hours = p.maintenance_hours
                        for name in s.affected:
                            self._emit(actions, "maintenance_request", name, "drastic reduction stage reached",
                                       hours=p.maintenance_hours)
                        failed = any(maintenance.get(n) is False for n in s.affected)
                        timed_out = now - s.maintenance_since >= MAINTENANCE_ATTEMPT_SECONDS
                        unconfirmed = any(maintenance.get(n) is not True for n in s.affected)
                        if failed or (timed_out and unconfirmed):
                            self._shutdown(actions, "maintenance failed or not confirmed within budget")
        elif sample.online and valid_age:
            s.seen_online = True
            if s.online_since is None:
                s.online_since = now
            stable = max(0, now - s.online_since)
            enough_to_restore = valid_energy and remaining > p.runtime_reserve_seconds + p.grace_seconds
            if s.outage_since is not None and stable >= p.recovery_stable_seconds and (
                    sample.charge is not None and sample.charge >= p.recovery_charge_percent) and enough_to_restore:
                for name in s.affected:
                    if s.stage in (1, 2) and hosts.get(name, HostFacts()).awake is True:
                        self._emit(actions, "restore_power", name, "mains recovery qualified",
                                   preserve_original_baseline=True)
                wake_safe = stable >= p.wake_stable_seconds and sample.charge >= p.wake_charge_percent
                for name in s.shutdown_planned:
                    if name in s.awake_before and name not in s.recovery_targets:
                        s.recovery_targets.append(name)
                for name in s.recovery_targets:
                    fact = hosts.get(name, HostFacts())
                    if fact.awake is True:
                        self._emit(actions, "check_readiness", name, "expected host confirmed awake")
                    elif wake_safe:
                        if name not in s.wake_started_at:
                            s.wake_started_at[name] = now
                        interval = p.wake_retry_initial_seconds
                        if now - s.wake_started_at[name] >= p.wake_retry_backoff_after_seconds:
                            interval = p.wake_retry_later_seconds
                        last = s.wake_last_at.get(name)
                        if last is None or now - last >= interval:
                            attempt = s.wake_attempts.get(name, 0) + 1
                            s.wake_attempts[name] = attempt
                            s.wake_last_at[name] = now
                            self._emit(actions, "wake", name, "recovery target not confirmed awake",
                                       attempt=attempt, packet_sent=False)
                for name in s.affected:
                    fact = hosts.get(name, HostFacts())
                    if s.maintenance_since is not None and fact.awake is True and fact.ready and maintenance.get(name) is not False:
                        self._emit(actions, "maintenance_cancel", name, "host readiness confirmed",
                                   owned_windows_only=True)
                # Planned requests are not treated as confirmed effects. Keep
                # the incident until explicit host/readiness and cloud facts
                # show complete recovery, including absent maintenance.
                complete = all(hosts.get(n, HostFacts()).awake is True and
                               hosts[n].ready and (s.maintenance_since is None or maintenance.get(n) is False)
                               for n in s.affected)
                if complete:
                    s.outage_since = None
                    s.stage = 0
                    s.clock_uncertain = False
                    s.maintenance_since = None
                    s.maintenance_hours = 0
                    s.shutdown_planned.clear()
                    s.recovery_targets.clear()
                    s.wake_attempts.clear()
                    s.wake_last_at.clear()
                    s.wake_started_at.clear()
                    s.affected.clear()

        if s.maintenance_since is not None and s.maintenance_hours and s.outage_since is not None:
            end = s.maintenance_since + s.maintenance_hours * 3600
            if now >= end - p.maintenance_renew_before_seconds:
                # Calculate total coverage without an unbounded loop after a
                # long Pi outage. This is desired coverage, NOT an API claim.
                hours = s.maintenance_hours * 2
                while now >= s.maintenance_since + hours * 3600 - p.maintenance_renew_before_seconds:
                    hours *= 2
                s.maintenance_hours = hours
                for name in s.affected:
                    self._emit(actions, "maintenance_extend", name, "incident remains unresolved",
                               hours=hours, provider_semantics_verified=False)
        return actions
