from __future__ import annotations

import http.client
import json
import threading
from contextlib import contextmanager

import pytest

from quantbt.studio.server import StudioServer


@contextmanager
def running_server(tmp_path):
    server = StudioServer(0, tmp_path / "studio.sqlite", tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def request(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        return response.status, response.read(), dict(response.getheaders())
    finally:
        connection.close()


def test_static_assets_and_request_boundaries(tmp_path):
    with running_server(tmp_path) as server:
        code, body, headers = request(server, "GET", "/")
        assert code == 200 and b"Agent research studio" in body
        assert "Content-Security-Policy" in headers
        assert request(server, "GET", "/../../LICENSE")[0] == 404
        assert request(server, "GET", "/api/runs", headers={"Host": "attacker.test"})[0] == 403
        assert request(server, "POST", "/api/runs", "{}")[0] == 403
        token = json.loads(request(server, "GET", "/api/session")[1])["token"]
        trusted = {
            "Origin": f"http://127.0.0.1:{server.server_port}",
            "X-Studio-Token": token,
            "Content-Type": "application/json",
        }
        assert request(server, "POST", "/api/runs", "[]", trusted)[0] == 400
        assert request(server, "POST", "/api/runs", '{"capital":NaN}', trusted)[0] == 400
        assert (
            request(server, "POST", "/api/runs", '{"source":"https://elsewhere"}', trusted)[0]
            == 400
        )
        assert (
            request(
                server, "POST", "/api/runs", "{}", {**trusted, "Origin": "http://attacker.test"}
            )[0]
            == 403
        )


def test_job_capacity_and_saved_events(tmp_path, monkeypatch):
    release = threading.Event()

    def execute(store, run_id, settings, root, reviewer):
        release.wait(timeout=3)
        store.finish(run_id, {"done": True})

    monkeypatch.setattr("quantbt.studio.server.execute", execute)
    with running_server(tmp_path) as server:
        try:
            headers = {
                "Origin": f"http://127.0.0.1:{server.server_port}",
                "X-Studio-Token": server.token,
                "Content-Type": "application/json",
            }
            status, body, _ = request(server, "POST", "/api/runs", "{}", headers)
            assert status == 202
            run_id = json.loads(body)["id"]
            assert request(server, "POST", "/api/runs", "{}", headers)[0] == 409
            assert request(server, "GET", f"/api/runs/{run_id}/events?after=-1")[0] == 400
            server.store.event(run_id, "quant", "COMPLETED", {"verdict": "APPROVE"})
            events = json.loads(request(server, "GET", f"/api/runs/{run_id}/events")[1])
            assert events[0]["detail"]["verdict"] == "APPROVE"
        finally:
            release.set()


def test_second_server_cannot_recover_an_active_database(tmp_path):
    with running_server(tmp_path) as server:
        run_id = server.store.create({})
        with pytest.raises(ValueError, match="own the database"):
            StudioServer(0, tmp_path / "studio.sqlite", tmp_path)
        assert server.store.get(run_id)["status"] == "RUNNING"
        server.store.finish(run_id, {"done": True})
