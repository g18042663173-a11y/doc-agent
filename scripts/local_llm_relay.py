from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from doc_agent.llm.mock_client import MockLLMClient


class RelayRequest(BaseModel):
    prompt: str
    model: str | None = None
    response_format: dict[str, Any] | None = None


app = FastAPI(title="Doc Agent Local LLM Relay")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "provider": "stub-relay"}


@app.post("/generate_json")
@app.post("/v1/generate_json")
def generate_json(request: RelayRequest) -> dict[str, Any]:
    return {"json": MockLLMClient().generate_json(request.prompt)}


@app.post("/v1/chat/completions")
def chat_completions(payload: dict[str, Any]) -> dict[str, Any]:
    messages = payload.get("messages") or []
    prompt = "\n".join(str(message.get("content", "")) for message in messages if isinstance(message, dict))
    result = MockLLMClient().generate_json(prompt)
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(result, ensure_ascii=False),
                }
            }
        ]
    }


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("LOCAL_LLM_RELAY_HOST", "127.0.0.1"),
        port=int(os.getenv("LOCAL_LLM_RELAY_PORT", "8765")),
        reload=False,
    )
