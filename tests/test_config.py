from pathlib import Path

import pytest

from ups_helper.config import Config, ConfigError, load_config


def load(tmp_path, body):
    path = tmp_path / 'config.yaml'
    path.write_text(body, encoding='utf-8')
    return load_config(path)


def test_defaults_and_explicit_profiles(tmp_path):
    config = load(tmp_path, '''version: 1
mode: observe
service:
  state_path: /tmp/state.json
hosts:
  - name: machine-1
    enabled: true
    wake_mac: 'aa:bb:cc:dd:ee:ff'
    light:
      cpu_pl1_watts: 50
      gpu_watts: {GPU-abcd: 100}
    drastic:
      cpu_pl1_watts: 30
      gpu_watts: {GPU-abcd: 60}
''')
    assert config.mode == 'observe'
    assert config.nut == Config().nut
    assert config.service.state_path == Path('/tmp/state.json')
    assert config.hosts[0].drastic.gpu_watts == {'GPU-abcd': 60.0}
    assert config.hosts[0].enabled is True


@pytest.mark.parametrize('body', [
    '', 'mode: observe', 'version: 1', 'version: true\nmode: observe',
    'version: 1\nmode: active',
    'version: 1\nmode: observe\nmode: observe',
    'version: 1\nmode: observe\nnut: {host: one, host: two}',
    'version: 1\nmode: observe\nssh: {}',
    'version: 1\nmode: observe\nhosts: [{name: foo, command: reboot}]',
    'version: 1\nmode: observe\nnut: {timeout_seconds: true}',
    'version: 1\nmode: observe\nnut: {timeout_seconds: .inf}',
    'version: 1\nmode: observe\npolicy: {grace_seconds: .nan}',
    'version: 1\nmode: observe\nservice: {poll_seconds: 0}',
    'version: 1\nmode: observe\npolicy: {grace_seconds: 130, drastic_after_seconds: 120}',
    'version: 1\nmode: observe\npolicy: {drastic_after_seconds: 300}',
    'version: 1\nmode: observe\npolicy: {critical_charge_percent: 50}',
    'version: 1\nmode: observe\npolicy: {wake_charge_percent: 49}',
    'version: 1\nmode: observe\npolicy: {maintenance_hours: 2.0}',
    'version: 1\nmode: observe\nhosts: [{name: x}, {name: x}]',
    'version: 1\nmode: observe\nhosts: [{name: ups-controller}]',
    'version: 1\nmode: observe\nhosts: [{name: 123}]',
    'version: 1\nmode: observe\nhosts: [{name: " x"}]',
    'version: 1\nmode: observe\nhosts: [{name: "x; reboot"}]',
    'version: 1\nmode: observe\nhosts: [{name: x, wake_mac: bad}]',
    'version: 1\nmode: observe\nhosts: [{name: x, enabled: 1}]',
    'version: 1\nmode: observe\nhosts: [{name: x, light: {cpu_pl1_watts: 30}, drastic: {cpu_pl1_watts: 40}}]',
    'version: 1\nmode: observe\nhosts: [{name: x, light: {gpu_watts: {g: 30}}, drastic: {gpu_watts: {g: 40}}}]',
    'version: 1\nmode: observe\nhosts: [{name: x, light: {gpu_watts: {g: 0}}}]',
    'version: 1\nmode: observe\nservice: &service {}\nnut: *service',
    'version: 1\nmode: observe\nnut: !!python/object/apply:os.system [echo dangerous]',
])
def test_invalid_configs_fail_closed(tmp_path, body):
    with pytest.raises(ConfigError):
        load(tmp_path, body)


def test_size_limit(tmp_path):
    with pytest.raises(ConfigError):
        load(tmp_path, 'version: 1\nmode: observe\n#' + 'x' * (1024 * 1024))


@pytest.mark.parametrize('setting', [
    'wake_stable_seconds: 119',
    'wake_retry_later_seconds: 29',
    'maintenance_renew_before_seconds: 7200',
    'runtime_reserve_seconds: 0',
    'unknown_shutdown_seconds: 0',
])
def test_invalid_policy_relationships(tmp_path, setting):
    with pytest.raises(ConfigError):
        load(tmp_path, 'version: 1\nmode: observe\npolicy: {' + setting + '}')


@pytest.mark.parametrize('host', ['example.com', '127.0.0.2', 'LOCALHOST', '0.0.0.0'])
def test_nut_host_must_be_supported_loopback(tmp_path, host):
    with pytest.raises(ConfigError):
        load(tmp_path, 'version: 1\nmode: observe\nnut: {host: "' + host + '"}')


@pytest.mark.parametrize('ups', ['bad name', 'bad#name', 'bad=name', 'bad"name', 'bad\\name', 'å'])
def test_nut_ups_must_be_protocol_token(tmp_path, ups):
    import json
    with pytest.raises(ConfigError):
        load(tmp_path, 'version: 1\nmode: observe\nnut: {ups: ' + json.dumps(ups) + '}')


@pytest.mark.parametrize('host', ['localhost', '127.0.0.1', '::1'])
def test_nut_supported_loopback(tmp_path, host):
    assert load(tmp_path, 'version: 1\nmode: observe\nnut: {host: "' + host + '"}').nut.host == host


def test_policy_relationship_boundaries_are_accepted(tmp_path):
    config = load(tmp_path, '''version: 1
mode: observe
policy:
  recovery_stable_seconds: 120
  wake_stable_seconds: 120
  wake_retry_initial_seconds: 30
  wake_retry_later_seconds: 30
  maintenance_renew_before_seconds: 7199
  runtime_reserve_seconds: 1
  unknown_shutdown_seconds: 1
''')
    assert config.policy.wake_stable_seconds == config.policy.recovery_stable_seconds
    assert config.policy.wake_retry_later_seconds == config.policy.wake_retry_initial_seconds
