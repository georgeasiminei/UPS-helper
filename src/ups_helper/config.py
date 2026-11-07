"""Strict, observe-only configuration loading."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
import re
from typing import Any, Dict, Optional, Tuple

import yaml
from yaml.events import AliasEvent


class ConfigError(ValueError):
    """Configuration is malformed or unsafe to use."""


@dataclass(frozen=True)
class NutConfig:
    host: str = '127.0.0.1'
    port: int = 3493
    ups: str = 'eaton5p'
    timeout_seconds: float = 3.0
    max_source_age_seconds: float = 30.0


@dataclass(frozen=True)
class ServiceConfig:
    poll_seconds: float = 2.0
    state_path: Path = Path('/var/lib/ups-helper/state.json')
    heartbeat_seconds: float = 60.0
    controller_id: str = 'ups-controller'


@dataclass(frozen=True)
class PolicyConfig:
    grace_seconds: float = 60.0
    drastic_after_seconds: float = 120.0
    shutdown_after_seconds: float = 300.0
    runtime_reserve_seconds: float = 480.0
    runtime_uncertainty_seconds: float = 60.0
    drastic_runtime_margin_seconds: float = 180.0
    drastic_charge_percent: float = 50.0
    critical_charge_percent: float = 20.0
    recovery_stable_seconds: float = 120.0
    recovery_charge_percent: float = 50.0
    wake_stable_seconds: float = 300.0
    wake_charge_percent: float = 80.0
    unknown_shutdown_seconds: float = 60.0
    maintenance_hours: int = 2
    maintenance_renew_before_seconds: float = 900.0
    wake_retry_initial_seconds: float = 30.0
    wake_retry_later_seconds: float = 300.0
    wake_retry_backoff_after_seconds: float = 300.0


@dataclass(frozen=True)
class PowerProfile:
    cpu_pl1_watts: Optional[float] = None
    cpu_pl2_watts: Optional[float] = None
    gpu_watts: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class HostConfig:
    name: str
    enabled: bool = False
    wake_mac: Optional[str] = None
    wake_broadcast: str = '255.255.255.255'
    light: PowerProfile = field(default_factory=PowerProfile)
    drastic: PowerProfile = field(default_factory=PowerProfile)


@dataclass(frozen=True)
class Config:
    version: int = 1
    mode: str = 'observe'
    nut: NutConfig = field(default_factory=NutConfig)
    service: ServiceConfig = field(default_factory=ServiceConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    hosts: Tuple[HostConfig, ...] = ()


class _StrictLoader(yaml.SafeLoader):
    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(AliasEvent):
            raise ConfigError('YAML aliases are not allowed')
        return super().compose_node(parent, index)


def _mapping(loader: _StrictLoader, node: yaml.nodes.MappingNode) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str):
            raise ConfigError('mapping keys must be strings')
        if key in result:
            raise ConfigError('duplicate key: {}'.format(key))
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)
_MAX_CONFIG_BYTES = 1024 * 1024
_HOST_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')
_MAC = re.compile(r'^(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$')


def _object(value: Any, allowed: set, where: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigError('{} must be a mapping'.format(where))
    unknown = set(value) - allowed
    if unknown:
        raise ConfigError('{} has unknown keys: {}'.format(where, ', '.join(sorted(unknown))))
    return value


def _string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError('{} must be a nonempty string'.format(where))
    return value


def _identifier(value: Any, where: str) -> str:
    result = _string(value, where)
    if result != result.strip():
        raise ConfigError(where + ' must not have surrounding whitespace')
    return result


def _number(value: Any, where: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError('{} must be a number'.format(where))
    try:
        result = float(value)
    except OverflowError as exc:
        raise ConfigError('{} must be finite'.format(where)) from exc
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        raise ConfigError('{} must be finite and {}'.format(where, 'positive' if positive else 'nonnegative'))
    return result


def _profile(value: Any, where: str) -> PowerProfile:
    data = _object(value, {'cpu_pl1_watts', 'cpu_pl2_watts', 'gpu_watts'}, where)
    values: Dict[str, Any] = {}
    for key in ('cpu_pl1_watts', 'cpu_pl2_watts'):
        if key in data:
            values[key] = None if data[key] is None else _number(data[key], where + '.' + key, positive=True)
    if 'gpu_watts' in data:
        gpu = data['gpu_watts']
        if not isinstance(gpu, dict):
            raise ConfigError(where + '.gpu_watts must be a mapping')
        values['gpu_watts'] = {_identifier(k, where + '.gpu_watts key'): _number(v, where + '.gpu_watts.' + k, positive=True) for k, v in gpu.items()}
    return PowerProfile(**values)


def _host(value: Any, index: int) -> HostConfig:
    where = 'hosts[{}]'.format(index)
    data = _object(value, {'name', 'enabled', 'wake_mac', 'wake_broadcast', 'light', 'drastic'}, where)
    if 'name' not in data:
        raise ConfigError(where + '.name is required')
    values: Dict[str, Any] = {'name': _identifier(data['name'], where + '.name')}
    if not _HOST_ID.fullmatch(values['name']):
        raise ConfigError(where + '.name must be a safe host identifier')
    if 'enabled' in data:
        if not isinstance(data['enabled'], bool):
            raise ConfigError(where + '.enabled must be a boolean')
        values['enabled'] = data['enabled']
    if 'wake_mac' in data:
        mac = data['wake_mac']
        if mac is not None and (not isinstance(mac, str) or not _MAC.fullmatch(mac)):
            raise ConfigError(where + '.wake_mac must be a colon-separated MAC address')
        values['wake_mac'] = mac
    if 'wake_broadcast' in data:
        values['wake_broadcast'] = _string(data['wake_broadcast'], where + '.wake_broadcast')
    for key in ('light', 'drastic'):
        if key in data:
            values[key] = _profile(data[key], where + '.' + key)
    host = HostConfig(**values)
    for key in ('cpu_pl1_watts', 'cpu_pl2_watts'):
        light, drastic = getattr(host.light, key), getattr(host.drastic, key)
        if light is not None and drastic is not None and drastic > light:
            raise ConfigError(where + ': drastic ' + key + ' exceeds light')
    for gpu in host.light.gpu_watts.keys() & host.drastic.gpu_watts.keys():
        if host.drastic.gpu_watts[gpu] > host.light.gpu_watts[gpu]:
            raise ConfigError(where + ': drastic GPU cap exceeds light for ' + gpu)
    return host


def load_config(path: Path) -> Config:
    """Load and validate a size-limited YAML configuration."""
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(_MAX_CONFIG_BYTES + 1)
        if len(raw) > _MAX_CONFIG_BYTES:
            raise ConfigError('configuration file is too large')
        data = yaml.load(raw, Loader=_StrictLoader)
    except (OSError, yaml.YAMLError, UnicodeError) as exc:
        raise ConfigError('cannot load configuration: {}'.format(exc)) from exc
    data = _object(data, {'version', 'mode', 'nut', 'service', 'policy', 'hosts'}, 'config')
    if 'version' not in data or type(data['version']) is not int or data['version'] != 1:
        raise ConfigError('version must be explicitly set to 1')
    if data.get('mode') != 'observe' or not isinstance(data.get('mode'), str):
        raise ConfigError('mode must be explicitly set to observe')

    nut_data = _object(data.get('nut', {}), set(NutConfig.__dataclass_fields__), 'nut')
    nut_values: Dict[str, Any] = {}
    for key, value in nut_data.items():
        if key == 'host':
            if value not in ('localhost', '127.0.0.1', '::1'):
                raise ConfigError('nut.host must be a supported loopback address')
            nut_values[key] = value
        elif key == 'ups':
            value = _string(value, 'nut.ups')
            if any(ord(char) < 33 or ord(char) > 126 or char in '"\\#=' for char in value):
                raise ConfigError('nut.ups must be a valid NUT token')
            nut_values[key] = value
        elif key == 'port':
            if type(value) is not int or not 1 <= value <= 65535:
                raise ConfigError('nut.port must be an integer between 1 and 65535')
            nut_values[key] = value
        else:
            nut_values[key] = _number(value, 'nut.' + key, positive=True)
    service_data = _object(data.get('service', {}), set(ServiceConfig.__dataclass_fields__), 'service')
    service_values: Dict[str, Any] = {}
    for key, value in service_data.items():
        if key == 'state_path':
            service_values[key] = Path(_string(value, 'service.state_path'))
        elif key == 'controller_id':
            service_values[key] = _identifier(value, 'service.controller_id')
        else:
            service_values[key] = _number(value, 'service.' + key, positive=True)
    policy_data = _object(data.get('policy', {}), set(PolicyConfig.__dataclass_fields__), 'policy')
    policy_values: Dict[str, Any] = {}
    for key, value in policy_data.items():
        if key == 'maintenance_hours':
            if type(value) is not int or value != 2:
                raise ConfigError('policy.maintenance_hours must be 2')
            policy_values[key] = value
        else:
            policy_values[key] = _number(value, 'policy.' + key, positive=key.startswith('wake_retry_') or key in ('runtime_reserve_seconds', 'unknown_shutdown_seconds'))
    policy = PolicyConfig(**policy_values)
    if not policy.grace_seconds <= policy.drastic_after_seconds < policy.shutdown_after_seconds:
        raise ConfigError('policy requires grace_seconds <= drastic_after_seconds < shutdown_after_seconds')
    if not policy.critical_charge_percent < policy.drastic_charge_percent <= 100:
        raise ConfigError('policy requires critical_charge_percent < drastic_charge_percent <= 100')
    if not policy.recovery_charge_percent <= policy.wake_charge_percent <= 100:
        raise ConfigError('policy requires recovery_charge_percent <= wake_charge_percent <= 100')
    if policy.wake_stable_seconds < policy.recovery_stable_seconds:
        raise ConfigError('wake stability must be at least recovery stability')
    if policy.wake_retry_later_seconds < policy.wake_retry_initial_seconds:
        raise ConfigError('later wake retry must be at least the initial retry')
    if policy.maintenance_renew_before_seconds >= policy.maintenance_hours * 3600:
        raise ConfigError('maintenance renewal must be less than the maintenance duration')
    host_data = data.get('hosts', [])
    if not isinstance(host_data, list):
        raise ConfigError('hosts must be a list')
    hosts = tuple(_host(item, i) for i, item in enumerate(host_data))
    names = [host.name for host in hosts]
    service = ServiceConfig(**service_values)
    if len(set(names)) != len(names):
        raise ConfigError('host names must be unique')
    if service.controller_id in names:
        raise ConfigError('controller_id must differ from host names')
    return Config(nut=NutConfig(**nut_values), service=service, policy=policy, hosts=hosts)
