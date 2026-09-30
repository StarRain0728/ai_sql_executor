import time

from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

import logging

from core.context import UserContext, set_user_context

logger = logging.getLogger(__name__)


async def logging_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    start_time = time.time()

    body = await request.body()

    # 只记录请求头名，不落原始值：Authorization/Cookie 等凭据一旦写入日志即造成信息泄露
    logger.info(f"[REQ]{request.method} {request.url} headers={list(request.headers.keys())} body={body.decode(errors='ignore')}")
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
