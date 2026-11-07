import os
import stat

import pytest

from ups_helper.store import CheckpointStore, StateError


def test_round_trip_and_permissions(tmp_path):
    path = tmp_path / "state.json"
    store = CheckpointStore(path)
    assert store.load() is None
    store.save({"version": 1, "state": {"a": 1}})
    assert store.load() == {"version": 1, "state": {"a": 1}}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("data", [b'{', b'[]', b'{"version":2}', b'{"version":true}', b'{"version":1,"x":NaN}', b'{"version":1,"x":1e999}', b'{"version":1,"version":1}', b'x' * (1024 * 1024 + 1)])
def test_corrupt_checkpoint_is_an_error(tmp_path, data):
    path = tmp_path / "state.json"
    path.write_bytes(data)
    with pytest.raises(StateError):
        CheckpointStore(path).load()
    assert path.read_bytes() == data


def test_pre_replace_failure_preserves_file_and_cleans_temp(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    store = CheckpointStore(path)
    store.save({"version": 1, "old": True})

    def fail(*args):
        raise OSError("failure")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(StateError):
        store.save({"version": 1, "old": False})
    assert store.load() == {"version": 1, "old": True}
    assert list(tmp_path.iterdir()) == [path]


def test_nonblocking_lock(tmp_path):
    store = CheckpointStore(tmp_path / "state.json")
    with store.locked():
        with pytest.raises(StateError):
            with store.locked():
                pass
    with store.locked():
        pass
