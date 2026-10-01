"""Domain errors raised by services and turned into HTTP responses by the app."""


class AppError(Exception):
    status_code = 400

    def __init__(self, detail: str, headers: dict[str, str] | None = None):
        super().__init__(detail)
        self.detail = detail
        self.headers = headers


class BadRequest(AppError):
    status_code = 400


class Forbidden(AppError):
    status_code = 403


class NotFound(AppError):
    status_code = 404


class Conflict(AppError):
    status_code = 409


class Unavailable(AppError):
    status_code = 503


class TooManyRequests(AppError):
    status_code = 429

    def __init__(self, retry_after: int):
        unit = "second" if retry_after == 1 else "seconds"
        super().__init__(
            f"Too many requests. Try again in {retry_after} {unit}.",
            headers={"Retry-After": str(retry_after)},
        )
        self.retry_after = retry_after
