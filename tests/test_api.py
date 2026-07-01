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


def test_monitoring_run_endpoint(monkeypatch):
    async def _fake_execute(command, cwd=None):
        assert command == "echo hello"
        assert cwd == "repo"
        return {
            "shell": "powershell",
            "cwd": "repo",
            "stdout": "hello\n",
            "stderr": "",
            "returncode": 0,
        }

    monkeypatch.setattr(api, "execute_shell_command", _fake_execute)

    response = client.post(
        "/monitoring/run", json={"command": "echo hello", "cwd": "repo"}
    )

    assert response.status_code == 200
    assert response.json()["shell"] == "powershell"
    assert response.json()["returncode"] == 0


def test_monitoring_stream_endpoint(monkeypatch):
    async def _fake_stream(command, cwd=None):
        assert command == "tail -f app.log"
        assert cwd == "repo"
        yield {"type": "start", "shell": "bash", "cwd": "repo"}
        yield {"type": "stdout", "content": "line-1\n"}
        yield {"type": "end", "returncode": 0}

    monkeypatch.setattr(api, "execute_shell_command_stream", _fake_stream)

    response = client.post(
        "/monitoring/stream", json={"command": "tail -f app.log", "cwd": "repo"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    payloads = [json.loads(line.removeprefix("data: ")) for line in lines]

    assert payloads[0]["type"] == "start"
    assert payloads[1]["type"] == "stdout"
    assert payloads[2]["type"] == "end"


def test_monitoring_analyze_stream_endpoint(monkeypatch):
    async def _fake_analyze(command, logs, cwd=None, model=None, context=None):
        assert command == "tail -f app.log"
        assert "line-1" in logs
        assert cwd == "repo"
        assert model == "qwen3.6"
        assert context == "API returns 500 on login"
        yield {"type": "insight_delta", "content": "Looks healthy."}
        yield {"type": "insight_done"}

    monkeypatch.setattr(api, "analyze_monitoring_logs_stream", _fake_analyze)

    response = client.post(
        "/monitoring/analyze/stream",
        json={
            "command": "tail -f app.log",
            "logs": "line-1\n",
            "cwd": "repo",
            "model": "qwen3.6",
            "context": "API returns 500 on login",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    payloads = [json.loads(line.removeprefix("data: ")) for line in lines]

    assert payloads[0]["type"] == "insight_delta"
    assert payloads[1]["type"] == "insight_done"
