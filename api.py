from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import logging
from main import (
    analyze_monitoring_logs_stream,
    execute_shell_command,
    execute_shell_command_stream,
    explain_code,
    generate_code,
    generate_code_stream,
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExplainCodeRequest(BaseModel):
    query: str
    path: str
    model: str | None = None


class MonitoringCommandRequest(BaseModel):
    command: str
    cwd: str | None = None


class MonitoringAnalyzeRequest(BaseModel):
    command: str
    logs: str
    cwd: str | None = None
    model: str | None = None
    context: str | None = None


@app.post("/explain_code")
async def explain_code_endpoint(request: ExplainCodeRequest):
    explanation = await explain_code(request.query, request.path, model=request.model)
    return {"explanation": explanation}


@app.post("/generate_code")
async def generate_code_endpoint(request: ExplainCodeRequest):
    await generate_code(request.query, request.path, model=request.model)
    return {"message": "Code generated successfully"}


@app.post("/generate_code/stream", response_class=StreamingResponse)
async def generate_code_stream_endpoint(request: ExplainCodeRequest):
    async def event_stream():
        async for event in generate_code_stream(
            request.query, request.path, model=request.model
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/monitoring/run")
async def monitoring_run_endpoint(request: MonitoringCommandRequest):
    result = await execute_shell_command(request.command, cwd=request.cwd)
    return result


@app.post("/monitoring/stream", response_class=StreamingResponse)
async def monitoring_stream_endpoint(request: MonitoringCommandRequest):
    async def event_stream():
        async for event in execute_shell_command_stream(
            request.command, cwd=request.cwd
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/monitoring/analyze/stream", response_class=StreamingResponse)
async def monitoring_analyze_stream_endpoint(request: MonitoringAnalyzeRequest):
    async def event_stream():
        async for event in analyze_monitoring_logs_stream(
            request.command,
            request.logs,
            cwd=request.cwd,
            model=request.model,
            context=request.context,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
