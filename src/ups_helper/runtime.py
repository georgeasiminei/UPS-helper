"""Observe-only monitoring and offline simulation orchestration."""
from __future__ import annotations

import json
import math
from pathlib import Path
import signal
import threading
import time
from typing import Any, Callable, Optional

from .config import Config
from .model import HostFacts, State, Telemetry
from .nut import NutClient, NutError
from .policy import Engine
from .store import CheckpointStore


def _emit(record: dict) -> None:
    print(json.dumps(record, allow_nan=False, separators=(',', ':')), flush=True)


def _action(action: Any, emit: Callable[[dict], None]) -> None:
    emit({'type': 'action', 'status': 'planned', 'executed': False, 'action': action.to_dict()})


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate scenario key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('non-finite scenario value')


def _fields(value, allowed, label):
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError('invalid ' + label)
    return value


def load_scenario(path: Path) -> list:
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('scenario too large')
        scenario = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('cannot load scenario') from exc
    _fields(scenario, {'events'}, 'scenario')
    events = scenario.get('events')
    if not isinstance(events, list):
        raise ValueError('scenario events must be a list')
    return events


def simulate(config: Config, scenario_path: Path, emit: Callable[[dict], None] = _emit) -> None:
    events = load_scenario(scenario_path)
    engine = Engine(config)
    action_count = 0
    previous_at = None
    for event in events:
        _fields(event, {'at', 'variables', 'hosts', 'maintenance'}, 'event')
        at = event.get('at')
        if isinstance(at, bool) or not isinstance(at, (int, float)):
            raise ValueError('event time must be a finite number')
        try:
            at = float(at)
        except OverflowError as exc:
            raise ValueError('event time must be a finite number') from exc
        if not math.isfinite(at) or at < 0 or (previous_at is not None and at < previous_at):
            raise ValueError('event times must be finite, nonnegative and ordered')
        previous_at = at
        variables = event.get('variables')
        if not isinstance(variables, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in variables.items()):
            raise ValueError('event variables must be string pairs')
        hosts_data = event.get('hosts', {})
        if not isinstance(hosts_data, dict) or not all(isinstance(k, str) for k in hosts_data):
            raise ValueError('event hosts must be a mapping')
        hosts = {}
        for name, facts in hosts_data.items():
            _fields(facts, {'awake', 'ready', 'shutdown_confirmed', 'boot_id'}, 'host facts')
            for key in ('ready', 'shutdown_confirmed'):
                if key in facts and type(facts[key]) is not bool:
                    raise ValueError('invalid host fact')
            if 'awake' in facts and facts['awake'] is not None and type(facts['awake']) is not bool:
                raise ValueError('invalid host fact')
            if 'boot_id' in facts and facts['boot_id'] is not None and not isinstance(facts['boot_id'], str):
                raise ValueError('invalid host fact')
            if facts.get('ready') is True and facts.get('awake') is not True:
                raise ValueError('ready host must be confirmed awake')
            if facts.get('shutdown_confirmed') is True and facts.get('awake') is not False:
                raise ValueError('confirmed shutdown must be confirmed asleep')
            hosts[name] = HostFacts(**facts)
        maintenance = event.get('maintenance', {})
        if not isinstance(maintenance, dict) or not all(isinstance(k, str) and type(v) is bool for k, v in maintenance.items()):
            raise ValueError('maintenance must be a boolean mapping')
        actions = engine.step(Telemetry.from_variables(variables, at), hosts, maintenance)
        for action in actions:
            _action(action, emit)
        action_count += len(actions)
    emit({'type': 'simulation_summary', 'events': len(events), 'actions': action_count, 'state': engine.state.to_dict()})


def monitor(config: Config, once: bool = False, state_path: Optional[Path] = None,
            emit: Callable[[dict], None] = _emit, stop_event: Optional[threading.Event] = None) -> None:
    if config.nut.host.lower() not in ('127.0.0.1', '::1', 'localhost'):
        raise ValueError('monitor requires a localhost NUT server')
    stop = stop_event if stop_event is not None else threading.Event()
    store = CheckpointStore(state_path if state_path is not None else config.service.state_path)
    old_handlers = {}
    if threading.current_thread() is threading.main_thread():
        def request_stop(signum, frame):
            stop.set()
        for signum in (signal.SIGINT, signal.SIGTERM):
            old_handlers[signum] = signal.signal(signum, request_stop)
    try:
        with store.locked():
            saved = store.load()
            state = State.from_dict(saved) if saved is not None else None
            engine = Engine(config, state)
            try:
                client = NutClient(config.nut.host, config.nut.port, config.nut.ups, config.nut.timeout_seconds)
            except NutError as exc:
                raise ValueError('invalid NUT client configuration') from exc
            persisted = saved
            last_heartbeat = None
            wall_anchor, monotonic_anchor = time.time(), time.monotonic()
            while not stop.is_set():
                try:
                    variables = client.read_variables()
                    available = True
                except NutError:
                    variables = {}
                    available = False
                # In-process NTP/manual wall-clock steps cannot shortcut a
                # recovery dwell. Cross-boot outage timing remains a planning
                # assumption and is not authorization for live control.
                now = wall_anchor + (time.monotonic() - monotonic_anchor)
                sample = Telemetry.from_variables(variables, now, config.nut.max_source_age_seconds)
                actions = engine.step(sample)
                current = engine.state.to_dict()
                meaningful = {k: v for k, v in current.items() if k != 'last_at'}
                prior = {k: v for k, v in persisted.items() if k != 'last_at'} if persisted is not None else None
                if meaningful != prior:
                    store.save(current)
                    persisted = current
                for action in actions:
                    _action(action, emit)
                monotonic = time.monotonic()
                if last_heartbeat is None or monotonic - last_heartbeat >= config.service.heartbeat_seconds:
                    emit({'type': 'status', 'at': now, 'nut_available': available,
                          'mode': 'observe', 'ups_status': sorted(sample.status),
                          'battery_charge_percent': sample.charge,
                          'battery_runtime_seconds': sample.runtime,
                          'assumed_source_age_bound_seconds': sample.source_age_seconds,
                          'policy_stage': engine.state.stage})
                    last_heartbeat = monotonic
                if once:
                    break
                stop.wait(config.service.poll_seconds)
            current = engine.state.to_dict()
            if current != persisted:
                store.save(current)
    finally:
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
