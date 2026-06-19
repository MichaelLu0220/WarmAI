from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from warmai.api.error_handlers import install_error_handlers
from warmai.api.routes.task_analysis import router
from warmai.config.logging_config import configure_logging
from warmai.config.settings import Settings, get_settings
from warmai.inference.adapters.base import InferenceAdapter
from warmai.inference.adapters.mock import MockAdapter
from warmai.inference.circuit_breaker import CircuitBreaker
from warmai.inference.service import InferenceService
from warmai.persistence.database import Database
from warmai.persistence.events import InferenceEventRepository
from warmai.persistence.idempotency import IdempotencyService
from warmai.persistence.migrations import run_migrations


def create_app(
    settings: Settings | None = None,
    *,
    adapter: InferenceAdapter | None = None,
) -> FastAPI:
    resolved = settings or get_settings()
    database = Database(resolved.database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(resolved.log_level)
        await run_migrations(database, Path("migrations"))
        yield

    app = FastAPI(title="WarmAI", version="1.0", lifespan=lifespan)
    app.state.settings = resolved
    app.state.database = database
    app.state.events = InferenceEventRepository(database)
    app.state.idempotency = IdempotencyService(
        database,
        ttl_seconds=resolved.pii_idempotency_ttl_seconds,
    )
    app.state.inference = InferenceService(
        adapter or MockAdapter(),
        CircuitBreaker(
            resolved.circuit_failure_threshold,
            resolved.circuit_recovery_seconds,
        ),
    )
    install_error_handlers(app)
    app.include_router(router)
    return app
