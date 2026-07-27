from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.log.config import setup_logger
from clients.factory import DatabaseClientFactory
from core.exceptions import register_exceptions_handlers


@asynccontextmanager
async def lifespan(_: FastAPI) -> None:
    yield
    DatabaseClientFactory.close_all_clients()


def create_app() -> FastAPI:
    app = FastAPI(title="SQL EXECUTOR API", version="0.0.1", lifespan=lifespan)
    app_logger = setup_logger()
    app.state.logger = app_logger
    from api.routes.sql import sql_router
    app.include_router(sql_router)
    from api.middleware import logging_middleware, context_middleware
    app.middleware("http")(logging_middleware)
    app.middleware("http")(context_middleware)
    register_exceptions_handlers(app)
    return app


app = create_app()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8680)
