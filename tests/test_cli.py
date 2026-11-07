import json
import socket
import subprocess

from ups_helper import cli, runtime
from ups_helper.nut import NutError


def config_file(tmp_path):
    path = tmp_path / 'config.yaml'
    path.write_text('version: 1\nmode: observe\n', encoding='utf-8')
    return path


def test_config_check_safe_summary(tmp_path, capsys):
    assert cli.main(['config-check', '--config', str(config_file(tmp_path))]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output['mode'] == 'observe'
    assert output['hosts'] == 0


def test_simulation_never_constructs_client_or_uses_network_or_processes(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError('offline simulation attempted external access')
    monkeypatch.setattr(runtime, 'NutClient', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    scenario = tmp_path / 'scenario.json'
    scenario.write_text(json.dumps({'events': [
        {'at': 1000, 'variables': {'ups.status': 'OL', 'battery.charge': '90'}},
        {'at': 1010, 'variables': {'ups.status': 'OB', 'battery.charge': '80'}},
    ]}), encoding='utf-8')
    assert cli.main(['simulate', '--config', str(config_file(tmp_path)), '--scenario', str(scenario)]) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[-1]['type'] == 'simulation_summary'
    assert lines[-1]['events'] == 2
    assert all(line['executed'] is False and line['status'] == 'planned' for line in lines[:-1])


def test_monitor_once_persists_checkpoint_and_unknown_on_nut_failure(tmp_path, monkeypatch, capsys):
    class FailedClient:
        def __init__(self, *args):
            pass
        def read_variables(self):
            raise NutError('sensitive details')
    monkeypatch.setattr(runtime, 'NutClient', FailedClient)
    state = tmp_path / 'state.json'
    assert cli.main(['monitor', '--config', str(config_file(tmp_path)), '--state', str(state), '--once']) == 0
    output = capsys.readouterr()
    assert 'sensitive details' not in output.out + output.err
    records = [json.loads(line) for line in output.out.splitlines()]
    assert any(record['type'] == 'status' and record['nut_available'] is False for record in records)
    assert json.loads(state.read_text())['version'] == 1


def test_monitor_rejects_corrupt_checkpoint_before_nut_access(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError('client created for corrupt state')
    monkeypatch.setattr(runtime, 'NutClient', forbidden)
    state = tmp_path / 'state.json'
    state.write_text('{broken', encoding='utf-8')
    assert cli.main(['monitor', '--config', str(config_file(tmp_path)), '--state', str(state), '--once']) == 2
    assert state.read_text() == '{broken'
    assert json.loads(capsys.readouterr().err)['type'] == 'error'


def test_simulation_rejects_unordered_times(tmp_path, capsys):
    scenario = tmp_path / 'scenario.json'
    scenario.write_text(json.dumps({'events': [
        {'at': 2, 'variables': {}}, {'at': 1, 'variables': {}}
    ]}), encoding='utf-8')
    assert cli.main(['simulate', '--config', str(config_file(tmp_path)), '--scenario', str(scenario)]) == 2
    assert json.loads(capsys.readouterr().err)['type'] == 'error'


def test_monitor_rejects_invalid_state_schema(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError('client created for invalid state')
    monkeypatch.setattr(runtime, 'NutClient', forbidden)
    state = tmp_path / 'state.json'
    state.write_text('{"version": 1, "last_at": true}', encoding='utf-8')
    assert cli.main(['monitor', '--config', str(config_file(tmp_path)), '--state', str(state), '--once']) == 2
    assert json.loads(capsys.readouterr().err)['type'] == 'error'


def test_monitor_rejects_remote_nut(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError('remote client created')
    monkeypatch.setattr(runtime, 'NutClient', forbidden)
    config = tmp_path / 'remote.yaml'
    config.write_text('version: 1\nmode: observe\nnut: {host: example.com}\n', encoding='utf-8')
    assert cli.main(['monitor', '--config', str(config), '--state', str(tmp_path / 'state'), '--once']) == 2
    assert json.loads(capsys.readouterr().err)['type'] == 'error'
