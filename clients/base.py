import time
from abc import ABC, abstractmethod
from typing import Any

from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

import logging

from core.context import UserContext, set_user_context

logger = logging.getLogger(__name__)


class DatabaseClient(ABC):
    def __init__(self, datasource_config) -> None:
        self.datasource_config = datasource_config

    @abstractmethod
    def execute(self, sql: str) -> tuple[list[str], list[dict[str, Any]]]:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


async def logging_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    start_time = time.time()

    body = await request.body()

    logger.info(f"[REQ]{request.method} {request.url} header={request.headers} body={body.decode(errors='ignore')}")
    response = await call_next(request)

    cost = time.time() - start_time

    logger.info(f"[RES]{response.status_code} {request.url} cost={cost:.4f}s")

    return response


async def context_middleware(request: Request, call_next: RequestResponseEndpoint):
    user_code = request.headers.get("X-User-Code")
    user_ctx = None
    if user_code:
        user_ctx = UserContext(user_code=user_code)
    set_user_context(user_ctx)
    return await call_next(request)
