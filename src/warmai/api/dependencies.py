import secrets

from fastapi import Header, Request

from warmai.api.error_handlers import ApiProblem
from warmai.contracts.errors import ErrorCode


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> None:
    expected = request.app.state.settings.api_key.get_secret_value()
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise ApiProblem(401, ErrorCode.UNAUTHORIZED, "Invalid API key.")
