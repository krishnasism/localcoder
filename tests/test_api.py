import json

from fastapi.testclient import TestClient

import api


client = TestClient(api.app)


def test_explain_code_endpoint(monkeypatch):
    async def _fake_explain(query, path):
        assert query == "what"
        assert path == "file.py"
        return "explanation"

    monkeypatch.setattr(api, "explain_code", _fake_explain)

    response = client.post("/explain_code", json={"query": "what", "path": "file.py"})

    assert response.status_code == 200
    assert response.json() == {"explanation": "explanation"}


def test_generate_code_endpoint_non_stream(monkeypatch):
    called = {"value": False}

    async def _fake_generate(query, path):
        called["value"] = True
        assert query == "do"
        assert path == "repo"

    monkeypatch.setattr(api, "generate_code", _fake_generate)

    response = client.post("/generate_code", json={"query": "do", "path": "repo"})

    assert response.status_code == 200
    assert response.json() == {"message": "Code generated successfully"}
    assert called["value"] is True


def test_generate_code_endpoint_stream(monkeypatch):
    async def _fake_stream(query, path):
        assert query == "do"
        assert path == "repo"
        yield {"type": "status", "step": "planning", "message": "start"}
        yield {"type": "final", "step": "completed", "summary": "done"}

    monkeypatch.setattr(api, "generate_code_stream", _fake_stream)

    response = client.post(
        "/generate_code/stream", json={"query": "do", "path": "repo"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    payloads = [json.loads(line.removeprefix("data: ")) for line in lines]

    assert payloads[0]["type"] == "status"
    assert payloads[1]["type"] == "final"
