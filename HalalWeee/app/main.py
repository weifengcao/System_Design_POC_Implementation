from __future__ import annotations

from fastapi import FastAPI

from .api import register_routers
from .core.logging import configure_logging
from .database import Base, engine

configure_logging()
Base.metadata.create_all(bind=engine)


def create_app() -> FastAPI:
    app = FastAPI(
        title="HalalWeee Catalog & Certification API",
        description="Initial slice providing certification and product management with halal safeguards.",
        version="0.1.0",
    )

    register_routers(app)

    @app.get("/", tags=["Health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
