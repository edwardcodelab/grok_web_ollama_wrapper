import asyncio
import json
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse
import uvicorn
from typing import Dict, Any
import uuid

app = FastAPI(title="Grok → Ollama Wrapper (Port 11434)")

# Global bridge
connected_client: WebSocket | None = None
pending_requests: Dict[str, asyncio.Queue] = {}

@app.get("/api/tags")
async def tags():
    return {"models": [{"name": "grok", "modified_at": time.time(), "size": 0}]}

async def send_to_grok(prompt: str, request_id: str):
    global connected_client
    if not connected_client:
        raise Exception("No Grok browser connected. Open grok.com with userscript active.")

    await connected_client.send_json({
        "type": "send_prompt",
        "prompt": prompt,
        "request_id": request_id
    })
    queue = asyncio.Queue()
    pending_requests[request_id] = queue
    return queue

@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    stream = body.get("stream", True)
    model = body.get("model", "grok")

    last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "Hello")

    request_id = str(uuid.uuid4())
    queue = await send_to_grok(last_user_msg, request_id)

    async def event_stream():
        try:
            while True:
                chunk = await queue.get()
                if chunk == "__DONE__":
                    yield 'data: {"done": true}\n\n'
                    break
                yield f'data: {json.dumps({"model": model, "created_at": time.time(), "message": {"role": "assistant", "content": chunk}, "done": False})}\n\n'
                await asyncio.sleep(0.01)
        except Exception as e:
            yield f'data: {json.dumps({"error": str(e)})}\n\n'

    if stream:
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    else:
        full = ""
        while True:
            chunk = await queue.get()
            if chunk == "__DONE__":
                break
            full += chunk
        return {"model": model, "message": {"role": "assistant", "content": full}, "done": True}

@app.post("/api/generate")
async def generate(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")
    return await chat(Request(scope={"type": "http", "method": "POST", "headers": []}, receive=lambda: None))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global connected_client
    await websocket.accept()
    connected_client = websocket
    print("✅ Grok userscript connected on port 11434!")
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "response_chunk":
                req_id = data["request_id"]
                if req_id in pending_requests:
                    await pending_requests[req_id].put(data["chunk"])
            elif data.get("type") == "response_done":
                req_id = data["request_id"]
                if req_id in pending_requests:
                    await pending_requests[req_id].put("__DONE__")
                    del pending_requests[req_id]
    except WebSocketDisconnect:
        print("❌ Userscript disconnected")
        connected_client = None
    finally:
        connected_client = None

if __name__ == "__main__":
    print("🚀 Starting Grok Ollama Wrapper on http://localhost:11434")
    print("   WebSocket bridge on ws://localhost:11434/ws")
    print("   Keep grok.com tab open with userscript active!")
    uvicorn.run(app, host="127.0.0.1", port=11434)
