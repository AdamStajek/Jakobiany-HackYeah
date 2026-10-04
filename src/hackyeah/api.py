from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from urllib.error import URLError

from fastapi import (
    APIRouter,
    Body,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
)
from pydantic import ValidationError

from hackyeah import auth, missions, needs, photos, places, search_ai
from hackyeah import models as m
from hackyeah.database import Store, atomic
from hackyeah.mobility_data import mobility_map
from hackyeah.mobility_routing import plan_mobility_route
from hackyeah.temporary_data import get_weather


class EndpointNotImplementedError(Exception):
    pass


ResourceId = Annotated[str, Path(min_length=1)]
Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query()]

router = APIRouter(
    prefix="/api/v1",
    responses={
        400: {"model": m.ErrorResponse, "description": "Niepoprawny JSON żądania."},
        501: {
            "model": m.ErrorResponse,
            "description": "Logika operacji nie jest zaimplementowana.",
        },
        422: {"model": m.ErrorResponse, "description": "Niepoprawne dane żądania."},
    },
)


@router.post("/auth/register", response_model=m.User, status_code=201, tags=["auth"])
def register(body: m.RegisterRequest, request: Request, response: Response) -> m.User:
    return auth.register(body, request, response)


@router.post("/auth/login", response_model=m.Session, tags=["auth"])
def login(body: m.LoginRequest, request: Request, response: Response) -> m.Session:
    return auth.login(body, request, response)


@router.get("/auth/session", response_model=m.Session, tags=["auth"])
def get_session(request: Request, response: Response) -> m.Session:
    response.headers["Cache-Control"] = "no-store"
    return auth.get_session(request)


@router.post("/auth/logout", status_code=204, response_model=None, tags=["auth"])
def logout(request: Request, response: Response) -> None:
    auth.logout(request, response)


@router.post(
    "/needs/interpret",
    response_model=m.InterpretResponse,
    tags=["needs"],
    responses={503: {"model": m.ErrorResponse}},
)
async def interpret_needs(
    body: m.InterpretRequest, response: Response
) -> m.InterpretResponse:
    response.headers["Cache-Control"] = "no-store"
    return await needs.interpret(body.description)


@router.post(
    "/places/interpret",
    response_model=search_ai.PlaceProposal,
    tags=["places"],
    responses={503: {"model": m.ErrorResponse}},
)
async def interpret_place_search(
    body: search_ai.SearchPrompt, response: Response
) -> search_ai.PlaceProposal:
    response.headers["Cache-Control"] = "no-store"
    return await search_ai.interpret_places(body)


@router.post(
    "/routes/interpret",
    response_model=search_ai.RouteProposal,
    tags=["routes"],
    responses={503: {"model": m.ErrorResponse}},
)
async def interpret_route_search(
    body: search_ai.SearchPrompt, response: Response
) -> search_ai.RouteProposal:
    response.headers["Cache-Control"] = "no-store"
    return await search_ai.interpret_route(body)


@router.get("/profiles", response_model=m.Page[m.Profile], tags=["profiles"])
def list_profiles(
    request: "Request", response: "Response", limit: Limit = 20, cursor: Cursor = None
) -> m.Page[m.Profile]:
    from hackyeah import auth, profiles

    response.headers["Cache-Control"] = "no-store"
    return profiles.list_page(auth.require_session(request).id, limit, cursor)


@router.post("/profiles", response_model=m.Profile, status_code=201, tags=["profiles"])
def create_profile(
    body: m.ProfileCreate, request: "Request", response: "Response"
) -> m.Profile:
    from hackyeah import auth, profiles

    user = auth.require_session(request)
    auth.require_csrf(request)
    response.headers["Cache-Control"] = "no-store"
    return profiles.create(user.id, body)


@router.get("/profiles/{id}", response_model=m.Profile, tags=["profiles"])
def get_profile(id: ResourceId, request: "Request", response: "Response") -> m.Profile:
    from hackyeah import auth, profiles

    response.headers["Cache-Control"] = "no-store"
    return profiles.get(auth.require_session(request).id, id)


@router.patch("/profiles/{id}", response_model=m.Profile, tags=["profiles"])
def update_profile(
    id: ResourceId, body: m.ProfilePatch, request: "Request", response: "Response"
) -> m.Profile:
    from hackyeah import auth, profiles

    user = auth.require_session(request)
    auth.require_csrf(request)
    response.headers["Cache-Control"] = "no-store"
    return profiles.update(user.id, id, body)


@router.delete(
    "/profiles/{id}", status_code=204, response_model=None, tags=["profiles"]
)
def delete_profile(id: ResourceId, request: "Request", response: "Response") -> None:
    from hackyeah import auth, profiles

    user = auth.require_session(request)
    auth.require_csrf(request)
    response.headers["Cache-Control"] = "no-store"
    profiles.delete(user.id, id)


@router.post(
    "/place-submissions",
    response_model=m.PlaceSubmission,
    status_code=201,
    tags=["places"],
)
def create_place_submission(
    body: m.PlaceSubmissionCreate, request: Request, response: Response
) -> m.PlaceSubmission:
    from hackyeah import place_submissions

    response.headers["Cache-Control"] = "no-store"
    return place_submissions.create(auth.require_csrf(request), body)


@router.get(
    "/place-submissions", response_model=m.Page[m.PlaceSubmission], tags=["places"]
)
def list_place_submissions(
    request: Request,
    response: Response,
    limit: Limit = 20,
    cursor: Cursor = None,
    mine: bool = False,
) -> m.Page[m.PlaceSubmission]:
    from hackyeah import place_submissions

    response.headers["Cache-Control"] = "no-store"
    return place_submissions.list_page(
        auth.require_session(request), limit, cursor, mine
    )


@router.post(
    "/place-submissions/{id}/review", response_model=m.PlaceSubmission, tags=["places"]
)
def review_place_submission(
    id: ResourceId, body: m.ReportReview, request: Request, response: Response
) -> m.PlaceSubmission:
    from hackyeah import place_submissions

    response.headers["Cache-Control"] = "no-store"
    return place_submissions.review(auth.require_csrf(request), id, body)


@router.post("/places/search", response_model=m.PlaceSearchResponse, tags=["places"])
def search_places(
    body: m.PlaceSearchRequest, request: Request, response: Response
) -> m.PlaceSearchResponse:
    response.headers["Cache-Control"] = "no-store"
    constraints = body.constraints
    if body.profile_id is not None:
        from hackyeah import profiles

        constraints = profiles.get(
            auth.require_session(request).id, body.profile_id
        ).constraints
    return places.search(body, constraints)


@router.get("/places/{id:path}", response_model=m.PlaceDetails, tags=["places"])
def get_place(
    id: ResourceId,
    request: Request,
    response: Response,
    profile_id: Annotated[str | None, Query(min_length=1)] = None,
) -> m.PlaceDetails:
    response.headers["Cache-Control"] = "no-store"
    constraints = None
    if profile_id is not None:
        from hackyeah import profiles

        constraints = profiles.get(
            auth.require_session(request).id, profile_id
        ).constraints
    return places.get(id, constraints)


@router.get("/routes/points", response_model=m.Page[m.PlaceSummary], tags=["routes"])
def route_points(
    query: Annotated[str, Query(min_length=2, max_length=200)],
) -> m.Page[m.PlaceSummary]:
    return places.route_points(query)


@router.post("/routes/plan", response_model=m.RoutePlanResponse, tags=["routes"])
def plan_routes(body: m.RoutePlanRequest, request: Request) -> m.RoutePlanResponse:
    if body.profile_id is not None:
        from hackyeah import profiles

        profile = profiles.get(auth.require_session(request).id, body.profile_id)
        body = body.model_copy(
            update={"constraints": profile.constraints, "profile_id": None}
        )
    response = plan_mobility_route(body)
    if not response.routes:
        return response
    lon, lat = response.routes[0].geometry.coordinates[0]
    try:
        response.weather = get_weather(m.Coordinates(lat=lat, lon=lon), days=7)
    except (OSError, URLError, ValueError, KeyError, TypeError, ValidationError):
        response.warnings.append(
            "Nie udało się pobrać aktualnej pogody; ryzyka pogodowe pozostają nieznane."
        )
        return response
    response.warnings.extend(response.weather.warnings)
    departure = body.departure_at or datetime.now(UTC)
    for route in response.routes:
        arrival = departure + timedelta(seconds=route.estimated_duration_s or 0)
        if not any(
            h.starts_at <= arrival and h.ends_at > departure
            for h in response.weather.weather_hours
        ):
            response.warnings.append("Brak prognozy dla czasu przejścia trasy.")
        for segment in route.segments:
            segment.temporary_difficulties = [
                item
                for item in response.weather.items
                if item.starts_at is not None
                and item.ends_at is not None
                and item.starts_at <= arrival
                and item.ends_at > departure
            ]
    return response


@router.get("/routes/mobility", response_model=m.MobilityMap, tags=["routes"])
def route_mobility(
    response: Response,
    kind: Literal["stops", "parking", "vehicles"] = "stops",
) -> m.MobilityMap:
    response.headers["Cache-Control"] = "no-store"
    try:
        return mobility_map(kind)
    except (OSError, ValueError, KeyError):
        return m.MobilityMap(
            items=[],
            warnings=[
                "Nie udało się pobrać wybranej warstwy miejskiej mapy. Spróbuj ponownie."
            ],
            attribution=[],
        )


@router.post("/photos", response_model=m.PhotoCreated, status_code=201, tags=["photos"])
def upload_photo(
    request: Request,
    file: Annotated[
        UploadFile,
        File(description="JPEG, PNG lub WebP; docelowo maks. 10 MiB i 20 mln pikseli."),
    ],
    address: Annotated[str | None, Form(max_length=300)] = None,
    metric: Annotated[str | None, Form(max_length=100)] = None,
) -> m.PhotoCreated:
    user = auth.require_csrf(request)
    try:
        return photos.create(
            user.id,
            file.file.read(photos.MAX_BYTES + 1),
            address=address,
            metric=metric,
        )
    finally:
        file.file.close()


@router.get("/photos/{id}", response_model=m.Photo, tags=["photos"])
def get_photo(id: ResourceId, request: Request) -> m.Photo:
    return photos.get(auth.require_session(request), id)


@router.delete("/photos/{id}", status_code=204, response_model=None, tags=["photos"])
def delete_photo(id: ResourceId, request: Request) -> Response:
    photos.delete(auth.require_csrf(request), id)
    return Response(status_code=204)


@router.get(
    "/photos/{id}/content",
    tags=["photos"],
    response_class=Response,
    responses={
        200: {
            "content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}
        }
    },
)
def photo_content(id: ResourceId, request: Request) -> Response:
    return Response(
        content=photos.content(auth.require_session(request), id),
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


_bookmarks = Store[str, list[str]]("profiles.bookmarks")


@router.get("/bookmarks", response_model=list[str], tags=["profiles"])
def get_bookmarks(request: Request, response: Response) -> list[str]:
    response.headers["Cache-Control"] = "no-store"
    return _bookmarks.get(auth.require_session(request).id, [])


@router.put("/bookmarks", response_model=list[str], tags=["profiles"])
def save_bookmarks(
    body: Annotated[list[m.Id], Body(max_length=1000)],
    request: Request,
    response: Response,
) -> list[str]:
    user = auth.require_csrf(request)
    response.headers["Cache-Control"] = "no-store"
    values = list(dict.fromkeys(body))
    for place_id in values:
        places.get(place_id)
    with atomic:
        _bookmarks[user.id] = values
    return values


@router.get("/missions", response_model=list[m.Mission], tags=["missions"])
def list_missions(
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[m.Mission]:
    if (lat is None) != (lon is None):
        raise HTTPException(422, "VALIDATION_ERROR")
    near = (
        m.Coordinates(lat=lat, lon=lon) if lat is not None and lon is not None else None
    )
    return missions.catalog(near, offset)


@router.post(
    "/missions/verification-requests",
    response_model=list[m.Mission],
    status_code=201,
    tags=["missions"],
)
def request_verification_mission(
    body: m.MissionRequest, request: Request, response: Response
) -> list[m.Mission]:
    response.headers["Cache-Control"] = "no-store"
    auth.require_csrf(request)
    return missions.request_verification(body)


@router.get("/missions/progress", response_model=m.MissionActivity, tags=["missions"])
def mission_activity(request: Request, response: Response) -> m.MissionActivity:
    response.headers["Cache-Control"] = "no-store"
    return missions.activity(auth.require_session(request))


@router.get(
    "/missions/review-queue",
    response_model=m.Page[m.MissionProgress],
    tags=["missions"],
)
def mission_queue(
    request: Request, response: Response, limit: Limit = 20, cursor: Cursor = None
) -> m.Page[m.MissionProgress]:
    response.headers["Cache-Control"] = "no-store"
    return missions.queue(auth.require_session(request), limit, cursor)


@router.get("/missions/{id}", response_model=m.Mission, tags=["missions"])
def get_mission(id: ResourceId) -> m.Mission:
    return missions.get(id)


@router.post(
    "/missions/{id}/start", response_model=m.MissionProgress, tags=["missions"]
)
def start_mission(
    id: ResourceId, request: Request, response: Response
) -> m.MissionProgress:
    response.headers["Cache-Control"] = "no-store"
    return missions.start(auth.require_csrf(request), id)


@router.post(
    "/missions/{id}/submit", response_model=m.MissionProgress, tags=["missions"]
)
def submit_mission(
    id: ResourceId, body: m.MissionSubmit, request: Request, response: Response
) -> m.MissionProgress:
    response.headers["Cache-Control"] = "no-store"
    return missions.submit(auth.require_csrf(request), id, body)


@router.post(
    "/missions/progress/{id}/review",
    response_model=m.MissionProgress,
    tags=["missions"],
)
def review_mission(
    id: ResourceId, body: m.ReportReview, request: Request, response: Response
) -> m.MissionProgress:
    response.headers["Cache-Control"] = "no-store"
    return missions.review(auth.require_csrf(request), id, body)


@router.post("/reports", response_model=m.Report, status_code=201, tags=["reports"])
def create_report(
    body: m.ReportCreate, request: Request, response: Response
) -> m.Report:
    from hackyeah import reports

    user = auth.require_csrf(request)
    response.headers["Cache-Control"] = "no-store"
    return reports.create(user, body)


@router.get("/reports", response_model=m.Page[m.Report], tags=["reports"])
def list_reports(
    request: Request,
    response: Response,
    mine: Annotated[bool | None, Query()] = None,
    status: Annotated[m.ReportStatus | None, Query()] = None,
    limit: Limit = 20,
    cursor: Cursor = None,
) -> m.Page[m.Report]:
    from hackyeah import reports

    response.headers["Cache-Control"] = "no-store"
    return reports.list_page(auth.require_session(request), mine, status, limit, cursor)


@router.get("/reports/{id}", response_model=m.Report, tags=["reports"])
def get_report(id: ResourceId, request: Request, response: Response) -> m.Report:
    from hackyeah import reports

    response.headers["Cache-Control"] = "no-store"
    return reports.get(auth.require_session(request), id)


@router.patch("/reports/{id}", response_model=m.Report, tags=["reports"])
def update_report(
    id: ResourceId, body: m.ReportPatch, request: Request, response: Response
) -> m.Report:
    from hackyeah import reports

    user = auth.require_csrf(request)
    response.headers["Cache-Control"] = "no-store"
    return reports.update(user, id, body)


@router.post("/reports/{id}/review", response_model=m.Report, tags=["reports"])
def review_report(
    id: ResourceId, body: m.ReportReview, request: Request, response: Response
) -> m.Report:
    from hackyeah import reports

    user = auth.require_csrf(request)
    response.headers["Cache-Control"] = "no-store"
    return reports.review(user, id, body)


@router.get("/owner/places", response_model=m.Page[m.PlaceSummary], tags=["owner"])
def list_owner_places(
    request: Request, response: Response, limit: Limit = 20, cursor: Cursor = None
) -> m.Page[m.PlaceSummary]:
    from hackyeah import owner

    response.headers["Cache-Control"] = "no-store"
    return owner.list_page(auth.require_session(request), limit, cursor)


@router.put(
    "/owner/places/{id}/declaration",
    response_model=m.DeclarationResponse,
    tags=["owner"],
)
def declare_place(
    id: ResourceId, body: m.DeclarationRequest, request: Request, response: Response
) -> m.DeclarationResponse:
    from hackyeah import owner

    response.headers["Cache-Control"] = "no-store"
    return owner.declare(auth.require_csrf(request), id, body)
