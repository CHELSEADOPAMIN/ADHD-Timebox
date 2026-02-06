"""FastAPI server entrypoint for ADHD Tymebox."""

from __future__ import annotations

import argparse
import asyncio
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.routes import auth, calendar, chat, events, focus, health, parking, tasks
from core.events import build_idle_handler
from core.state import app_state
from tools.idle_watcher import IdleWatcher
from agents.orchestrator import OrchestratorAgent


def create_app(data_dir: str | None = None) -> FastAPI:
    if data_dir:
        os.environ["ADHD_DATA_DIR"] = data_dir

    app = FastAPI(title="ADHD Tymebox API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(tasks.router)
    app.include_router(events.router)
    app.include_router(focus.router)
    app.include_router(auth.router)
    app.include_router(parking.router)
    app.include_router(calendar.router)

    @app.on_event("startup")
    async def startup() -> None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(base_dir, ".."))
        load_dotenv(os.path.join(project_root, ".env"))
        load_dotenv(os.path.join(base_dir, ".env"), override=True)
        data_dir = os.getenv("ADHD_DATA_DIR")
        if data_dir:
            load_dotenv(os.path.join(data_dir, ".env"), override=True)

        if not (
            os.getenv("OPENONION_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        ):
            raise RuntimeError(
                "No LLM API key found. Set OPENONION_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY."
            )

        app_state.event_loop = asyncio.get_running_loop()
        app_state.event_queue = app_state.get_event_queue("default-user")

        orchestrator = app_state.get_orchestrator("default-user")
        app_state.orchestrator = orchestrator

        idle_watcher = IdleWatcher(
            context_tool=orchestrator.focus_agent.context_tool,
            on_idle=build_idle_handler(
                orchestrator, app_state.event_queue, app_state.event_loop
            ),
            interval_seconds=30,
            idle_threshold_seconds=300,
            cooldown_seconds=600,
            focus_only=True,
            routine_check_seconds=300,
        )
        idle_watcher.start()
        app_state.idle_watcher = idle_watcher

    @app.on_event("shutdown")
    async def shutdown() -> None:
        if app_state.idle_watcher:
            app_state.idle_watcher.stop()

    return app


app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ADHD Timebox API server")
    parser.add_argument("--data-dir", dest="data_dir", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.data_dir:
        os.environ["ADHD_DATA_DIR"] = args.data_dir

    uvicorn.run(create_app(args.data_dir), host=args.host, port=args.port)
