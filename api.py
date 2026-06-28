from fastapi import FastAPI
from pydantic import BaseModel

from main import explain_code, generate_code

app = FastAPI()


class ExplainCodeRequest(BaseModel):
    query: str
    path: str


@app.post("/explain_code")
def explain_code_endpoint(request: ExplainCodeRequest):
    explanation = explain_code(request.query, request.path)
    return {"explanation": explanation}


@app.post("/generate_code")
def generate_code_endpoint(request: ExplainCodeRequest):
    generate_code(request.query, request.path)
    return {"message": "Code generated successfully"}
