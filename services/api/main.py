"""FastAPI application entry point for ContextWeave."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.shared.models import init_db
from services.api.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ContextWeave API",
        description="Workspace-level knowledge graph with typed headers and cross-file queries",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")

    @app.on_event("startup")
    async def startup():
        init_db()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "contextweave-api"}

    return app


app = create_app()
