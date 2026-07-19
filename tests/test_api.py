import json

from fastapi.testclient import TestClient

import api


client = TestClient(api.app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_explain_code_endpoint(monkeypatch, tmp_path):
    target = tmp_path / "file.py"
    target.write_text("print('hi')\n", encoding="utf-8")

    async def _fake_explain(query, path, model=None):
        assert query == "what"
        assert path == str(target.resolve())
        return "explanation"

    monkeypatch.setattr(api, "explain_code", _fake_explain)

    response = client.post("/explain_code", json={"query": "what", "path": str(target)})

    assert response.status_code == 200
    assert response.json() == {"explanation": "explanation"}


def test_generate_code_rejects_missing_path():
    response = client.post(
        "/generate_code",
        json={"query": "do something", "path": "C:/does/not/exist/localcoder"},
    )
    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]


def test_generate_code_endpoint_non_stream(monkeypatch, tmp_path):
    called = {"value": False}

    async def _fake_generate(query, path, model=None):
        called["value"] = True
        assert query == "do"
        assert path == str(tmp_path.resolve())

    monkeypatch.setattr(api, "generate_code", _fake_generate)

    response = client.post(
        "/generate_code", json={"query": "do", "path": str(tmp_path)}
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Code generated successfully"}
    assert called["value"] is True


def test_generate_code_endpoint_stream(monkeypatch, tmp_path):
    async def _fake_stream(query, path, model=None, cancel_event=None):
        assert query == "do"
        assert path == str(tmp_path.resolve())
        yield {"type": "status", "step": "planning", "message": "start"}
        yield {"type": "final", "step": "completed", "summary": "done"}

    monkeypatch.setattr(api, "generate_code_stream", _fake_stream)

    response = client.post(
        "/generate_code/stream", json={"query": "do", "path": str(tmp_path)}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    payloads = [json.loads(line.removeprefix("data: ")) for line in lines]

    assert payloads[0]["type"] == "status"
    assert payloads[1]["type"] == "final"


def test_generate_code_rejects_empty_query(tmp_path):
    response = client.post(
        "/generate_code", json={"query": "   ", "path": str(tmp_path)}
    )
    assert response.status_code == 422
