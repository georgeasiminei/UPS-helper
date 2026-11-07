"""A bounded, read-only NUT client."""

import ipaddress
import socket
import time


class NutError(Exception):
    """The NUT server could not provide a valid variable listing."""


_MAX_LINE = 8192
_MAX_FRAME = 1024 * 1024
_MAX_LINES = 4096


def _tokens(line):
    """Parse NUT fields, including its quoting, escaping, and comment rules."""
    fields = []
    i = 0
    while i < len(line):
        if line[i] == " ":
            i += 1
            continue
        if line[i] == "#":
            break
        if line[i] == "=":
            fields.append("=")
            i += 1
            continue
        quoted = line[i] == '"'
        if quoted:
            i += 1
        value = []
        closed = not quoted
        while i < len(line):
            char = line[i]
            if char == "\\":
                i += 1
                if i == len(line):
                    raise NutError("Malformed NUT response")
                value.append(line[i])
                i += 1
            elif quoted and char == '"':
                i += 1
                closed = True
                break
            elif not quoted and char in " =#":
                break
            else:
                value.append(char)
                i += 1
        if not closed:
            raise NutError("Malformed NUT response")
        fields.append("".join(value))
    return fields


class NutClient:
    def __init__(self, host: str, port: int, ups: str, timeout_seconds: float = 3.0):
        if not isinstance(ups, str) or not ups or any(
            ord(c) < 33 or ord(c) > 126 or c in '"\\#=' for c in ups
        ):
            raise NutError("Invalid UPS name")
        if timeout_seconds <= 0:
            raise NutError("Invalid timeout")
        try:
            address = ipaddress.ip_address("127.0.0.1" if host == "localhost" else host)
            if not address.is_loopback or "%" in str(address):
                raise ValueError("not loopback")
        except ValueError as exc:
            raise NutError("NUT host must be a loopback IP address") from exc
        self.host = str(address)
        self._family = socket.AF_INET if address.version == 4 else socket.AF_INET6
        self.port = port
        self.ups = ups
        self.timeout_seconds = timeout_seconds

    def read_variables(self) -> dict[str, str]:
        deadline = time.monotonic() + self.timeout_seconds
        pending = b""
        total = 0
        count = 0

        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise NutError("NUT request timed out")
            return value

        try:
            with socket.socket(self._family, socket.SOCK_STREAM) as sock:
                sock.settimeout(remaining())
                sock.connect((self.host, self.port))
                sock.settimeout(remaining())
                sock.sendall(f"LIST VAR {self.ups}\n".encode("ascii"))

                def read_line():
                    nonlocal pending, total, count
                    while b"\n" not in pending:
                        if len(pending) > _MAX_LINE:
                            raise NutError("NUT response line too long")
                        sock.settimeout(remaining())
                        chunk = sock.recv(min(4096, _MAX_FRAME - total + 1))
                        if not chunk:
                            raise NutError("Incomplete NUT response")
                        total += len(chunk)
                        if total > _MAX_FRAME:
                            raise NutError("NUT response too large")
                        pending += chunk
                    raw, pending = pending.split(b"\n", 1)
                    count += 1
                    if len(raw) > _MAX_LINE or count > _MAX_LINES:
                        raise NutError("NUT response limit exceeded")
                    if raw.endswith(b"\r"):
                        raw = raw[:-1]
                    if any(c < 32 or c == 127 for c in raw):
                        raise NutError("Invalid NUT response")
                    try:
                        return _tokens(raw.decode("ascii"))
                    except UnicodeDecodeError as exc:
                        raise NutError("Invalid NUT response encoding") from exc

                if read_line() != ["BEGIN", "LIST", "VAR", self.ups]:
                    raise NutError("Invalid NUT response start")
                result = {}
                while True:
                    parts = read_line()
                    if parts == ["END", "LIST", "VAR", self.ups]:
                        return result
                    if len(parts) != 4 or parts[:2] != ["VAR", self.ups] or not parts[2]:
                        raise NutError("Invalid NUT response frame")
                    if parts[2] in result:
                        raise NutError("Duplicate NUT variable")
                    result[parts[2]] = parts[3]
        except NutError:
            raise
        except (OSError, ValueError, OverflowError) as exc:
            raise NutError("NUT request failed") from exc
