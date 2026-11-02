from fastapi import FastAPI

from organiser.routes import (
    action_requests,
    agent,
    approvals,
    brief,
    commitments,
    events,
    health,
    system,
    tasks,
)


def register(app: FastAPI) -> None:
    app.include_router(health.router)
    app.include_router(tasks.router)
    app.include_router(commitments.router)
    app.include_router(events.router)
    app.include_router(action_requests.router)
    app.include_router(brief.router)
    app.include_router(approvals.router)
    app.include_router(system.router)
    app.include_router(agent.router)
