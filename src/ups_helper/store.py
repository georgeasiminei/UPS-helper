"""Durable JSON checkpoints with an exclusive advisory writer lock."""

from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import tempfile


class StateError(Exception):
    """A checkpoint could not be safely loaded or saved."""


_MAX_SIZE = 1024 * 1024


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite number")
    return result


def _invalid_constant(value):
    raise ValueError("invalid JSON constant")


def _validate(state):
    if not isinstance(state, dict) or type(state.get("version")) is not int or state["version"] != 1:
        raise ValueError("unsupported checkpoint")


class CheckpointStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self):
        try:
            with self.path.open("rb") as stream:
                data = stream.read(_MAX_SIZE + 1)
            if len(data) > _MAX_SIZE:
                raise ValueError("checkpoint too large")
            state = json.loads(data.decode("utf-8"), object_pairs_hook=_object, parse_constant=_invalid_constant, parse_float=_finite_float)
            _validate(state)
            return state
        except FileNotFoundError:
            return None
        except (OSError, ValueError, UnicodeError, RecursionError) as exc:
            raise StateError("Could not load checkpoint") from exc

    def save(self, state: dict) -> None:
        temp_path = None
        try:
            _validate(state)
            data = json.dumps(state, allow_nan=False, separators=(",", ":")).encode("utf-8")
            if len(data) > _MAX_SIZE:
                raise ValueError("checkpoint too large")
            json.loads(data, object_pairs_hook=_object, parse_constant=_invalid_constant, parse_float=_finite_float)
            fd, name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
            temp_path = Path(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self.path)
            temp_path = None
            directory_fd = os.open(self.path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            raise StateError("Could not save checkpoint") from exc
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @contextmanager
    def locked(self):
        fd = None
        try:
            fd = os.open(str(self.path) + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if fd is not None:
                os.close(fd)
            raise StateError("Could not acquire checkpoint lock") from exc
        try:
            yield
        finally:
            os.close(fd)
