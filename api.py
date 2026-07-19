from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
import asyncio
import json
import logging
import os
from main import explain_code, generate_code, generate_code_stream

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Localcoder", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateCodeRequest(BaseModel):
    query: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)
    model: str | None = None

    @field_validator("query", "path")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned


def _validate_workspace_path(path: str) -> str:
    resolved = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(resolved):
        raise HTTPException(
            status_code=400,
            detail=f"Path does not exist: {resolved}",
        )
    return resolved


@app.get("/health")
async def health_endpoint():
    return {"status": "ok"}


@app.post("/explain_code")
async def explain_code_endpoint(request: GenerateCodeRequest):
    path = _validate_workspace_path(request.path)
    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail="explain_code requires a file path")
    explanation = await explain_code(request.query, path, model=request.model)
    return {"explanation": explanation}


@app.post("/generate_code")
async def generate_code_endpoint(request: GenerateCodeRequest):
    path = _validate_workspace_path(request.path)
    await generate_code(request.query, path, model=request.model)
    return {"message": "Code generated successfully"}


@app.post("/generate_code/stream", response_class=StreamingResponse)
async def generate_code_stream_endpoint(
    request: GenerateCodeRequest, http_request: Request
):
    path = _validate_workspace_path(request.path)
    cancel_event = asyncio.Event()

    async def event_stream():
        try:
            async for event in generate_code_stream(
                request.query,
                path,
                model=request.model,
                cancel_event=cancel_event,
            ):
                if await http_request.is_disconnected():
                    cancel_event.set()
                    logger.info("Client disconnected; cancelling agent run")
                    break
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            cancel_event.set()
            raise
        except Exception as exc:
            logger.exception("Streaming code generation failed")
            yield f"data: {json.dumps({'type': 'error', 'step': 'server', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
