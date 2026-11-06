from fastapi import FastAPI

from organiser.routes import (
    action_requests,
    agent,
    approvals,
    brief,
    catchup,
    commute,
    commitments,
    events,
    health,
    hooks,
    memory,
    shopping,
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
    app.include_router(shopping.router)
    app.include_router(memory.router)
    app.include_router(agent.router)
    app.include_router(catchup.router)
    app.include_router(commute.router)
    app.include_router(hooks.router)
