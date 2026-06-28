from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from main import explain_code, generate_code, generate_code_stream

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


@app.post("/explain_code")
async def explain_code_endpoint(request: ExplainCodeRequest):
    explanation = await explain_code(request.query, request.path)
    return {"explanation": explanation}


@app.post("/generate_code")
async def generate_code_endpoint(request: ExplainCodeRequest):
    await generate_code(request.query, request.path)
    return {"message": "Code generated successfully"}


@app.post("/generate_code/stream", response_class=StreamingResponse)
async def generate_code_stream_endpoint(request: ExplainCodeRequest):
    async def event_stream():
        async for event in generate_code_stream(request.query, request.path):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
