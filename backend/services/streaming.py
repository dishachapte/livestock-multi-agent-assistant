"""Live agent updates over Server-Sent Events (SSE).

The Manager runs in a background thread and pushes an event each time an agent finishes.
The HTTP response streams those events to the browser as they happen.
"""
import json
import queue
import threading

from backend.agents.manager import run_manager
from backend.database import SessionLocal

_DONE = object()


def stream_ask(question: str, lang: str):
    events: queue.Queue = queue.Queue()

    def worker():
        db = SessionLocal()  # each thread needs its own database session
        try:
            result = run_manager(db, question, lang, emit=events.put)
            events.put({"event": "final", "data": result})
        except Exception as exc:
            print(f"[stream error] {exc!r}")
            events.put({"event": "error", "data": {"message": "The assistant could not finish this question."}})
        finally:
            db.close()
            events.put(_DONE)

    threading.Thread(target=worker, daemon=True).start()

    while True:
        item = events.get()
        if item is _DONE:
            break
        payload = json.dumps(item["data"], default=str, ensure_ascii=False)
        yield f"event: {item['event']}\ndata: {payload}\n\n"
