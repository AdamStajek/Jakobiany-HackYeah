from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from hackyeah.api import EndpointNotImplementedError, router
from hackyeah.database import initialize
from hackyeah.models import APIError, ErrorDetail, ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    from hackyeah.confidence import recalculate_all

    recalculate_all()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Swoją Drogą API",
    version="0.1.0",
    description=(
        "Planowanie tras działa na sieci pieszej Krakowa z OSM i uwzględnia profil. Auth, profile, "
        "zdjęcia, zgłoszenia i deklaracje właścicieli zapisują dane w SQLite. "
        "Interpretacja potrzeb korzysta z OpenAI przez PydanticAI. "
        "Wyszukiwanie i szczegóły miejsc korzystają z bazy OSM. "
        "Docelowe zasady dostępu opisuje docs/kontrakt-frontend-backend.md."
    ),
)
app.include_router(router)


def error_response(
    status: int, code: str, message: str, details: list[ErrorDetail]
) -> JSONResponse:
    request_id = f"req_{uuid4().hex}"
    body = ErrorResponse(
        error=APIError(
            code=code,
            message=message,
            details=details,
            request_id=request_id,
        )
    )
    return JSONResponse(
        status_code=status,
        content=body.model_dump(),
        headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
    )


@app.exception_handler(EndpointNotImplementedError)
async def not_implemented(
    request: Request, exc: EndpointNotImplementedError
) -> JSONResponse:
    return error_response(
        501, "NOT_IMPLEMENTED", "Ta operacja nie jest jeszcze zaimplementowana.", []
    )


@app.exception_handler(RequestValidationError)
async def validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        ErrorDetail(
            field=".".join(
                str(part)
                for part in error["loc"]
                if part not in ("body", "query", "path")
            ),
            code="OUT_OF_RANGE"
            if error["type"]
            in {"greater_than", "greater_than_equal", "less_than", "less_than_equal"}
            else "INVALID_VALUE",
            message="Niepoprawna lub brakująca wartość pola.",
        )
        for error in exc.errors()
    ]
    malformed_json = any(error["type"] == "json_invalid" for error in exc.errors())
    return error_response(
        400 if malformed_json else 422,
        "INVALID_REQUEST" if malformed_json else "VALIDATION_ERROR",
        "Sprawdź dane żądania.",
        details,
    )


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    status = exc.status_code
    code = {
        400: "INVALID_REQUEST",
        401: "AUTH_REQUIRED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "FILE_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        503: "DEPENDENCY_UNAVAILABLE",
    }.get(status, "INTERNAL_ERROR" if status >= 500 else "INVALID_REQUEST")
    detail_codes = {
        "AUTH_REQUIRED",
        "INVALID_CREDENTIALS",
        "FORBIDDEN",
        "CSRF_FAILED",
        "CONFLICT",
        "PHOTO_IN_USE",
        "PHOTO_REJECTED",
        "FILE_TOO_LARGE",
        "UNSUPPORTED_MEDIA_TYPE",
        "VALIDATION_ERROR",
        "INVALID_REQUEST",
        "RATE_LIMITED",
        "DEPENDENCY_UNAVAILABLE",
        "NOT_FOUND",
        "INVALID_PHOTO",
        "INVALID_PHOTO_DIMENSIONS",
        "PHOTO_TOO_LARGE",
    }
    if isinstance(exc.detail, str) and exc.detail in detail_codes:
        code = exc.detail
    message = {
        400: "Niepoprawne żądanie.",
        401: "Wymagane jest zalogowanie.",
        403: "Brak uprawnień do tej operacji.",
        404: "Nie znaleziono zasobu.",
        409: "Operacja jest sprzeczna z aktualnym stanem.",
        413: "Plik przekracza dozwolony rozmiar.",
        415: "Nieobsługiwany format pliku.",
        422: "Sprawdź dane żądania.",
        429: "Zbyt wiele żądań.",
        503: "Usługa jest chwilowo niedostępna.",
    }.get(
        status, "Wewnętrzny błąd serwera." if status >= 500 else "Niepoprawne żądanie."
    )
    response = error_response(status, code, message, [])
    retry_after = (exc.headers or {}).get("Retry-After")
    if retry_after:
        response.headers["Retry-After"] = retry_after
    return response
