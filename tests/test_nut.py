import socket
import threading
import time

import pytest

from ups_helper.nut import NutClient, NutError


@pytest.fixture
def server():
    threads = []
    listeners = []

    def start(response, delay=0):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listeners.append(listener)
        requests = []

        def serve():
            conn, _ = listener.accept()
            with conn:
                requests.append(conn.recv(1024))
                if delay:
                    time.sleep(delay)
                try:
                    conn.sendall(response)
                except OSError:
                    pass

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        threads.append(thread)
        return listener.getsockname()[1], requests

    yield start
    for thread in threads:
        thread.join(timeout=1)
    for listener in listeners:
        listener.close()


def test_read_only_listing_and_quoted_values(server):
    port, requests = server(b'BEGIN LIST VAR ups\nVAR ups a "hello # world"\nVAR ups b "a \\\"quote\\\""\nEND LIST VAR ups\n')
    assert NutClient("127.0.0.1", port, "ups").read_variables() == {"a": "hello # world", "b": 'a "quote"'}
    assert requests == [b"LIST VAR ups\n"]


@pytest.mark.parametrize("response", [
    b'ERR UNKNOWN-UPS\n',
    b'BEGIN LIST VAR other\n',
    b'BEGIN LIST VAR ups\nVAR other a "1"\nEND LIST VAR ups\n',
    b'BEGIN LIST VAR ups\nVAR ups a "1"\nVAR ups a "2"\nEND LIST VAR ups\n',
    b'BEGIN LIST VAR ups\nEND LIST VAR other\n',
    b'BEGIN LIST VAR ups\nVAR ups a "unterminated\n',
    b'BEGIN LIST VAR ups\nVAR ups a "\xff"\n',
    b'BEGIN LIST VAR ups\n' + b'x' * 8193 + b'\n',
])
def test_rejects_bad_frames(server, response):
    port, _ = server(response)
    with pytest.raises(NutError):
        NutClient("127.0.0.1", port, "ups").read_variables()


def test_timeout(server):
    port, _ = server(b'', delay=0.1)
    with pytest.raises(NutError):
        NutClient("127.0.0.1", port, "ups", timeout_seconds=0.02).read_variables()


@pytest.mark.parametrize("name", ["", "ups\nSET VAR ups x y", "a b", 'a"b', "é"])
def test_rejects_invalid_names(name):
    with pytest.raises(NutError):
        NutClient("127.0.0.1", 3493, name)


def test_nut_quoting_escaping_and_comments(server):
    response = (b'BEGIN LIST VAR ups # comment\n'
                b"VAR ups a '100'\n"
                b'VAR ups b 1\\00\n'
                b'VAR ups c "one\\# two\\\\three\\\"four" # comment\n'
                b'END LIST VAR ups\n')
    port, _ = server(response)
    assert NutClient('localhost', port, 'ups').read_variables() == {
        'a': "'100'", 'b': '100', 'c': 'one# two\\three"four'
    }


@pytest.mark.parametrize('frame', [
    b'VAR ups a "bad\n',
    b'VAR ups a "bad\\\n',
    b'VAR ups a "one"two\n',
    b'VAR ups a = 1\n',
])
def test_rejects_malformed_fields(server, frame):
    port, _ = server(b'BEGIN LIST VAR ups\n' + frame + b'END LIST VAR ups\n')
    with pytest.raises(NutError):
        NutClient('127.0.0.1', port, 'ups').read_variables()


@pytest.mark.parametrize('host', ['example.com', '192.0.2.1', '0.0.0.0', '::', 'localhost.example.com'])
def test_rejects_nonloopback_hosts(host, monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail('must not resolve or connect')
    monkeypatch.setattr(socket, 'getaddrinfo', fail)
    monkeypatch.setattr(socket, 'socket', fail)
    with pytest.raises(NutError):
        NutClient(host, 3493, 'ups')


def test_loopback_connect_avoids_dns(server, monkeypatch):
    port, _ = server(b'BEGIN LIST VAR ups\nEND LIST VAR ups\n')
    def fail(*args, **kwargs):
        pytest.fail('must not resolve hostnames')
    monkeypatch.setattr(socket, 'getaddrinfo', fail)
    assert NutClient('localhost', port, 'ups').read_variables() == {}


@pytest.mark.parametrize('name', ['ups#x', 'ups=x'])
def test_rejects_name_with_nut_delimiters(name):
    with pytest.raises(NutError):
        NutClient('127.0.0.1', 3493, name)
