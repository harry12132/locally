"""Loopback HTTP and server-sent event interface for the local agent."""

import json
from collections.abc import Iterator
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from .agent_system import agent_app
from .database import initialize_database


app = FastAPI(title="Local Enterprise AI Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    thread_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=100)


class ApprovalRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100)
    approved: bool


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def generate_agent_stream(user_message: str, thread_id: str) -> Iterator[str]:
    inputs = {"messages": [HumanMessage(content=user_message)]}
    config = {"configurable": {"thread_id": thread_id}}
    try:
        for update in agent_app.stream(inputs, config=config, stream_mode="updates"):
            for node_name, state_update in update.items():
                if node_name == "__interrupt__":
                    for interrupt_event in state_update:
                        payload = {
                            "agent": "Email Drafting Subagent",
                            "content": interrupt_event.value,
                            "type": "approval_required",
                            "thread_id": thread_id,
                        }
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    continue
                active_agent = state_update.get("active_agent", "Supervisor")
                for message in state_update.get("messages", []):
                    if getattr(message, "tool_calls", None):
                        content = json.dumps(message.tool_calls)
                        event_type = "tool_call"
                    elif message.type == "tool":
                        content = message.content
                        event_type = "tool_result"
                    else:
                        content = message.content
                        event_type = "text"
                    payload = {
                        "agent": active_agent,
                        "node": node_name,
                        "content": content,
                        "type": event_type,
                        "thread_id": thread_id,
                    }
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    except Exception as error:
        payload = {
            "agent": "System",
            "content": str(error),
            "type": "error",
            "thread_id": thread_id,
        }
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    return StreamingResponse(
        generate_agent_stream(request.message, request.thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/approvals")
def approval_endpoint(request: ApprovalRequest):
    config = {"configurable": {"thread_id": request.thread_id}}
    snapshot = agent_app.get_state(config)
    if not any(task.interrupts for task in snapshot.tasks):
        raise HTTPException(status_code=409, detail="No pending approval for this chat.")

    try:
        result = agent_app.invoke(
            Command(resume={"approved": request.approved}), config=config
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail="The local email relay failed.") from error

    return {
        "status": "approved" if request.approved else "rejected",
        "message": result["messages"][-1].content,
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "model": "qwen2.5:3b", "database": "sqlite"}