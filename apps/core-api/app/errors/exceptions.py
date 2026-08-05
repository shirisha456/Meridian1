class AppError(Exception):
    """Base for every error a route deliberately raises.

    Subclasses set `status_code` and `error_type` as class attributes so a
    route only has to supply the human-readable message and, optionally,
    machine-readable `details`. `register_exception_handlers` turns any
    `AppError` into the `{"error": {...}}` envelope documented in
    docs/api.md — routes never need to build that shape by hand.
    """

    status_code: int = 500
    error_type: str = "internal_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    error_type = "not_found"


class ConflictError(AppError):
    status_code = 409
    error_type = "conflict"


class UnauthorizedError(AppError):
    status_code = 401
    error_type = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    error_type = "forbidden"


class ServiceUnavailableError(AppError):
    status_code = 503
    error_type = "service_unavailable"


class TooManyRequestsError(AppError):
    status_code = 429
    error_type = "too_many_requests"


class UnprocessableError(AppError):
    """Distinct from Pydantic's own 422 (error_type="validation_error",
    app/errors/handlers.py::validation_error_handler): this is for a
    request that's syntactically valid but can't be fulfilled given the
    current state of the data — e.g. generating an insight for a period
    with no categorized spending to summarize."""

    status_code = 422
    error_type = "unprocessable"
