from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StrictBool,
    StrictFloat,
    StrictInt,
    model_validator,
)

Id = Annotated[str, Field(min_length=1)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
Description = Annotated[str, Field(max_length=4000)]
NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Count = Annotated[StrictInt, Field(ge=0)]
Percent = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Surface = Literal["paved", "asphalt", "gravel", "cobblestone", "ground", "other"]
Smoothness = Literal[
    "excellent",
    "good",
    "intermediate",
    "bad",
    "very_bad",
    "horrible",
    "very_horrible",
    "impassable",
]
TemporaryCategory = Literal["heat", "icing", "snow", "construction"]
FactStatus = Literal["confirmed", "unconfirmed"]
ReportStatus = Literal["pending", "accepted", "rejected"]
Attribute = Literal[
    "steps_count",
    "steps_present",
    "threshold_height_cm",
    "kerb_height_cm",
    "raised_kerb",
    "lighting_available",
    "smoothness",
    "entrance_width_cm",
    "slope_percent",
    "ramp_available",
    "elevator_available",
    "accessible_toilet",
    "rest_area_available",
    "surface",
    "distance_without_rest_m",
    "heat_risk",
    "icing_risk",
    "snow_risk",
    "construction_present",
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Coordinates(Model):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]


class Constraints(Model):
    max_steps: Count | None
    max_threshold_cm: NonNegative | None
    require_lighting: StrictBool | None = None
    max_kerb_height_cm: NonNegative | None = None
    allowed_smoothness: Annotated[list[Smoothness], Field(min_length=1)] | None = None
    max_slope_percent: NonNegative | None
    min_entrance_width_cm: Positive | None
    max_distance_without_rest_m: Positive | None
    require_step_free_access: StrictBool | None
    require_accessible_toilet: StrictBool | None
    allowed_surfaces: Annotated[list[Surface], Field(min_length=1)] | None

    @model_validator(mode="after")
    def check_steps(self) -> Self:
        if self.require_step_free_access and self.max_steps not in (None, 0):
            raise ValueError("Dostęp bez stopni wymaga max_steps równego 0 lub null.")
        return self


class RegisterRequest(Model):
    email: EmailStr
    password: Annotated[SecretStr, Field(min_length=12, max_length=128)]
    display_name: Name


class LoginRequest(Model):
    email: EmailStr
    password: Annotated[SecretStr, Field(min_length=12, max_length=128)]


class User(Model):
    id: Id
    display_name: Name
    roles: list[str]


class Session(Model):
    user: User
    csrf_token: str


class ProfileCreate(Model):
    name: Name
    description: Description
    constraints: Constraints


class ProfilePatch(Model):
    name: Name | None = None
    description: Description | None = None
    constraints: Constraints | None = None

    @model_validator(mode="after")
    def check_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Przekaż co najmniej jedno pole profilu.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Przekazane pola profilu nie mogą być null.")
        return self


class Profile(ProfileCreate):
    id: Id
    created_at: AwareDatetime
    updated_at: AwareDatetime


class Page[T](Model):
    items: list[T]
    next_cursor: str | None


class InterpretRequest(Model):
    description: Annotated[str, Field(min_length=1, max_length=4000)]


class InterpretResponse(Model):
    constraints: Constraints
    summary: str
    questions: list[str]
    requires_confirmation: Literal[True]


class Source(Model):
    type: Literal["owner", "user", "ai", "osm", "weather", "other"]
    label: str
    url: str | None
    license: str | None
    retrieved_at: AwareDatetime
    modified_at: AwareDatetime | None = None


class Observation(Model):
    attribute: Attribute
    value: StrictInt | StrictFloat | StrictBool | Surface | Smoothness | None

    @model_validator(mode="after")
    def check_value(self) -> Self:
        if self.value is None:
            return self
        if self.attribute == "surface":
            valid = self.value in (
                "paved",
                "asphalt",
                "gravel",
                "cobblestone",
                "ground",
                "other",
            )
        elif self.attribute == "smoothness":
            valid = self.value in (
                "excellent",
                "good",
                "intermediate",
                "bad",
                "very_bad",
                "horrible",
                "very_horrible",
                "impassable",
            )
        elif self.attribute in {
            "ramp_available",
            "raised_kerb",
            "steps_present",
            "lighting_available",
            "elevator_available",
            "accessible_toilet",
            "rest_area_available",
            "heat_risk",
            "icing_risk",
            "snow_risk",
            "construction_present",
        }:
            valid = type(self.value) is bool
        elif self.attribute == "steps_count":
            valid = type(self.value) is int and self.value >= 0
        else:
            valid = (
                isinstance(self.value, (int, float))
                and not isinstance(self.value, bool)
                and self.value >= 0
            )
        if not valid:
            raise ValueError("Typ lub zakres value nie pasuje do attribute.")
        return self


class Fact(Observation):
    id: Id
    unit: Literal["count", "cm", "percent", "m"] | None
    status: FactStatus
    confidence_score: NonNegative = 0
    confidence_level: Literal["certain", "probable", "uncertain"] = "uncertain"
    confidence_calculated_at: AwareDatetime | None = None
    confidence_percent: Percent | None
    observed_at: AwareDatetime | None
    updated_at: AwareDatetime
    valid_until: AwareDatetime | None
    sources: list[Source]
    unconfirmed_reason: (
        Literal["missing", "conflicting", "stale", "pending_verification"] | None
    )


class AssessmentReason(Model):
    code: str
    message: str
    fact_ids: list[Id]


class Assessment(Model):
    status: Literal["meets_requirements", "does_not_meet_requirements", "uncertain"]
    summary: str
    reasons: list[AssessmentReason]


class Barrier(Model):
    category: TemporaryCategory | None = None
    id: Id
    kind: Literal["permanent", "temporary"]
    description: str
    location: Coordinates
    fact_ids: list[Id]
    starts_at: AwareDatetime | None
    ends_at: AwareDatetime | None
    status: FactStatus


class ProfileSelection(Model):
    constraints: Constraints | None = None
    profile_id: Id | None = None

    @model_validator(mode="after")
    def check_selection(self) -> Self:
        if self.constraints is not None and self.profile_id is not None:
            raise ValueError("Wybierz constraints albo profile_id.")
        return self


class PlaceSearchRequest(ProfileSelection):
    query: Annotated[str, Field(min_length=1, max_length=1000)]
    near: Coordinates | None = None
    radius_m: Annotated[float, Field(ge=100, le=20000)] = 2000
    include_uncertain: StrictBool = True
    limit: Annotated[int, Field(ge=1, le=100)] = 20
    cursor: str | None = None

    @model_validator(mode="after")
    def check_radius(self) -> Self:
        if "radius_m" in self.model_fields_set and self.near is None:
            raise ValueError("Przekazanie radius_m wymaga near.")
        return self


class PlacePhoto(Model):
    url: str
    original_url: str
    source_url: str
    title: str
    author: str
    credit: str = ""
    license: str
    license_url: str | None = None
    description: str = ""


class PlaceSummary(Model):
    id: Id
    name: str
    category: str
    address: str | None
    address_is_nearest: bool = False
    location: Coordinates
    distance_m: NonNegative | None
    assessment: Assessment
    facts: list[Fact]
    website: str | None = None
    phone: str | None = None
    opening_hours: str | None = None
    operator: str | None = None
    access: str | None = None
    photos: list[PlacePhoto] = Field(default_factory=list)


class PlaceSearchResponse(Page[PlaceSummary]):
    total_count: int
    warnings: list[str]
    attribution: list[Source]


class PlaceDetails(PlaceSummary):
    facts: list[Fact] = Field(
        description=(
            "Fakty dostępności miejsca. Wymagane kategorie: schody (steps_count), "
            "progi (threshold_height_cm), windy (elevator_available), szerokość "
            "wejść (entrance_width_cm), łazienki dla osób z niepełnosprawnościami "
            "(accessible_toilet). Brak wiedzy: value=null, status=unconfirmed, "
            "unconfirmed_reason=missing. Pozostałe kategorie zgodnie z kontraktem."
        ),
    )
    barriers: list[Barrier]
    updated_at: AwareDatetime
    attribution: list[Source]
    website_title: str | None = None
    website_description: str | None = None
    website_telephone: str | None = None
    website_opening_hours: str | None = None
    accessibility_summary: str | None = None
    website_source: Source | None = None

    @model_validator(mode="after")
    def check_accessibility_categories(self) -> Self:
        required = {
            "steps_count",
            "threshold_height_cm",
            "elevator_available",
            "entrance_width_cm",
            "accessible_toilet",
        }
        if required - {fact.attribute for fact in self.facts}:
            raise ValueError(
                "Miejsce musi zawierać wszystkie pięć kategorii dostępności."
            )
        return self


class PlaceReference(Model):
    place_id: Id


class RoutePlanRequest(ProfileSelection):
    origin: Coordinates | PlaceReference
    destination: Coordinates | PlaceReference
    departure_at: AwareDatetime | None = None
    mode: Literal["walk", "transit", "car"] = "walk"
    accessible_parking: StrictBool = False

    @model_validator(mode="after")
    def check_parking_mode(self) -> Self:
        if self.accessible_parking and self.mode != "car":
            raise ValueError("Wybór parkingu wymaga trybu samochodowego.")
        return self


class LineString(Model):
    type: Literal["LineString"]
    coordinates: Annotated[
        list[
            tuple[
                Annotated[float, Field(ge=-180, le=180)],
                Annotated[float, Field(ge=-90, le=90)],
            ]
        ],
        Field(min_length=2),
    ]


class Point(Model):
    type: Literal["Point"]
    coordinates: tuple[
        Annotated[float, Field(ge=-180, le=180)],
        Annotated[float, Field(ge=-90, le=90)],
    ]


class WeatherHour(Model):
    location: Coordinates
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    temperature_c: float | None
    apparent_temperature_c: float | None
    precipitation_starts_at: AwareDatetime
    precipitation_ends_at: AwareDatetime
    precipitation_mm: NonNegative | None
    snowfall_cm: NonNegative | None
    snow_depth_cm: NonNegative | None
    weather_code: Count | None
    heat_risk: StrictBool | None
    icing_risk: StrictBool | None
    snow_risk: StrictBool | None

    @model_validator(mode="after")
    def check_interval(self) -> Self:
        if (
            self.ends_at <= self.starts_at
            or self.precipitation_ends_at <= self.precipitation_starts_at
        ):
            raise ValueError(
                "Koniec okresu pogodowego musi być późniejszy niż początek."
            )
        return self


class TemporaryDifficulty(Model):
    id: Id
    kind: Literal["temporary"] = "temporary"
    category: TemporaryCategory
    description: str
    geometry: Point | LineString | None
    location_text: str | None
    starts_at: AwareDatetime | None
    ends_at: AwareDatetime | None
    updated_at: AwareDatetime
    valid_until: AwareDatetime
    status: FactStatus
    unconfirmed_reason: Literal["forecast", "pending_verification", "stale"] | None
    confidence_percent: Percent | None
    sources: Annotated[list[Source], Field(min_length=1)]
    pedestrian_access: Literal["unknown", "restricted", "closed", "open"] = "unknown"
    weather: WeatherHour | None = None
    source_fields: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_evidence(self) -> Self:
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValueError("Koniec utrudnienia musi być późniejszy niż początek.")
        if self.valid_until <= self.updated_at:
            raise ValueError(
                "Dane muszą mieć termin ważności późniejszy niż aktualizacja."
            )
        if self.status == "unconfirmed" and self.unconfirmed_reason is None:
            raise ValueError("Niepotwierdzone utrudnienie wymaga powodu.")
        if self.status == "confirmed" and self.unconfirmed_reason is not None:
            raise ValueError("Potwierdzone utrudnienie nie ma powodu niepotwierdzenia.")
        return self


class TemporaryDataSnapshot(Model):
    generated_at: AwareDatetime
    valid_until: AwareDatetime
    source: Literal["weather", "construction"]
    heat_threshold_c: float | None = None
    items: list[TemporaryDifficulty]
    weather_hours: list[WeatherHour] = Field(default_factory=list)
    attribution: list[Source]
    warnings: list[str]

    @model_validator(mode="after")
    def check_validity(self) -> Self:
        if self.valid_until <= self.generated_at:
            raise ValueError("Termin ważności musi być późniejszy niż czas pobrania.")
        return self


class RestPoint(Model):
    id: Id
    location: Coordinates
    description: str
    fact_ids: list[Id]


ROUTE_ATTRIBUTES = {
    "steps_count",
    "steps_present",
    "threshold_height_cm",
    "kerb_height_cm",
    "raised_kerb",
    "ramp_available",
    "surface",
    "smoothness",
    "lighting_available",
}


class RouteSegment(Model):
    id: Id
    distance_m: NonNegative
    instruction: str
    geometry: LineString
    assessment: Assessment
    facts: list[Fact]
    barriers: list[Barrier]
    rest_points: list[RestPoint]
    mode: Literal["walk", "transit", "car"] = "walk"
    line: str | None = None
    departure_at: AwareDatetime | None = None
    arrival_at: AwareDatetime | None = None
    delay_s: int | None = None
    from_stop: str | None = None
    to_stop: str | None = None
    temporary_difficulties: list[TemporaryDifficulty] = Field(
        default_factory=list,
        description="Czasowe ryzyka: upał, oblodzenie, śnieg i remonty. Pusta lista nie potwierdza pokrycia źródeł.",
    )

    @model_validator(mode="after")
    def check_route_categories(self) -> Self:
        if ROUTE_ATTRIBUTES - {fact.attribute for fact in self.facts}:
            raise ValueError(
                "Odcinek musi zawierać wszystkie kategorie dostępności trasy."
            )
        return self


class Route(Model):
    variant: Literal["fastest", "constrained"] | None = None
    id: Id
    distance_m: NonNegative
    estimated_duration_s: NonNegative | None
    assessment: Assessment
    geometry: LineString
    segments: list[RouteSegment]
    facts: list[Fact]
    computed_at: AwareDatetime
    mode: Literal["walk", "transit", "car"] = "walk"
    parking: "MobilityPoint | None" = None


class MobilityPoint(Model):
    id: Id
    name: str
    location: Coordinates
    kind: Literal["stop", "parking", "vehicle"]
    line: str | None = None
    updated_at: AwareDatetime | None = None


class MobilityMap(Model):
    items: list[MobilityPoint]
    warnings: list[str]
    attribution: list[Source]


class RoutePlanResponse(Model):
    weather: TemporaryDataSnapshot | None = Field(
        default=None,
        description="Prognoza pobrana w locie; null oznacza brak aktualnej prognozy, nie brak ryzyka.",
    )
    routes: Annotated[list[Route], Field(max_length=3)]
    warnings: list[str]
    attribution: list[Source]


class PhotoCreated(Model):
    id: Id
    status: Literal["processing", "ready"]
    created_at: AwareDatetime


class Photo(Model):
    id: Id
    status: Literal["processing", "ready", "rejected"]
    preview_url: str | None
    error_code: str | None
    description: str = ""
    address: str | None = None
    metric: str | None = None


class ReportTarget(Model):
    type: Literal["place", "segment"]
    id: Id


class ReportCreate(Model):
    target: ReportTarget
    kind: Literal["correction", "confirmation", "missing_data"]
    fact_id: Id | None = None
    description: Description | None = None
    observations: list[Observation] = Field(default_factory=list)
    photo_ids: Annotated[list[Id], Field(max_length=5)] = Field(default_factory=list)
    observed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def check_content(self) -> Self:
        if self.kind in ("correction", "confirmation") and self.fact_id is None:
            raise ValueError("Korekta lub potwierdzenie wymaga fact_id.")
        if not (self.description or self.observations or self.photo_ids):
            raise ValueError("Przekaż opis, obserwację lub zdjęcie.")
        if self.observed_at is not None and self.observed_at > datetime.now(UTC):
            raise ValueError("Data obserwacji nie może wskazywać przyszłości.")
        return self


class ReportPatch(Model):
    description: Description | None = None
    observations: list[Observation] | None = None
    photo_ids: Annotated[list[Id], Field(max_length=5)] | None = None

    @model_validator(mode="after")
    def check_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Przekaż co najmniej jedno pole zgłoszenia.")
        for field in ("observations", "photo_ids"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError("Kolekcje nie mogą być null.")
        return self


class AIProposal(Observation):
    confidence_percent: Percent
    explanation: str


class Report(Model):
    id: Id
    author_id: Id
    target: ReportTarget
    kind: Literal["correction", "confirmation", "missing_data"]
    fact_id: Id | None
    description: Description | None
    observations: list[Observation]
    photo_ids: Annotated[list[Id], Field(max_length=5)]
    status: ReportStatus
    ai_status: Literal["not_requested", "pending", "completed", "failed"]
    ai_proposals: list[AIProposal]
    review_comment: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    observed_at: AwareDatetime | None = None


class ReportReview(Model):
    decision: Literal["accepted", "rejected"]
    comment: Annotated[str, Field(min_length=1, max_length=4000)]
    accepted_ai_proposal_indexes: list[Count] = Field(default_factory=list)


class Mission(Model):
    priority: Literal[1, 2, 3] = 3
    target_type: Literal["place", "segment"] = "place"
    location: Coordinates | None = None
    available: bool = True
    id: Id
    place_id: Id
    place_name: str
    address: str | None = None
    address_is_nearest: bool = False
    title: str
    fact_id: Id
    attribute: Attribute
    points: Count
    time_minutes: Count


class MissionRequest(Model):
    place_id: Id
    fact_ids: Annotated[list[Id], Field(min_length=1, max_length=30)]


class RouteMissionRequest(Model):
    fact_id: Id
    attribute: Attribute
    instruction: Annotated[str, Field(min_length=1, max_length=300)]
    location: Coordinates


class MissionSubmit(Model):
    description: Annotated[str, Field(max_length=4000)] | None = None
    observations: list[Observation] = Field(default_factory=list)
    photo_ids: Annotated[list[Id], Field(min_length=1, max_length=5)]


class MissionProgress(Model):
    id: Id
    mission_id: Id
    user_id: Id
    status: Literal["in_progress", "pending", "accepted", "rejected"]
    ai_status: Literal["not_requested", "pending", "completed", "failed"] = (
        "not_requested"
    )
    report_id: Id | None
    answer: str
    awarded_points: Count
    review_comment: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class MissionActivity(Model):
    items: list[MissionProgress]
    points: Count
    contributor_title: str = "Krakowski Odkrywca"


class DeclarationRequest(Model):
    observations: Annotated[list[Observation], Field(min_length=1)]
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def check_attributes(self) -> Self:
        attributes = [observation.attribute for observation in self.observations]
        if len(attributes) != len(set(attributes)):
            raise ValueError("Atrybuty obserwacji nie mogą się powtarzać.")
        return self


class DeclarationResponse(Model):
    place_id: Id
    facts: list[Fact]
    updated_at: AwareDatetime


class ErrorDetail(Model):
    field: str
    code: str
    message: str


class APIError(Model):
    code: str
    message: str
    details: list[ErrorDetail]
    request_id: str


class ErrorResponse(Model):
    error: APIError


class RouteDataProperties(Model):
    node_ids: list[int]
    tags: dict[str, str]
    facts: list[Fact]


class RouteDataFeature(Model):
    type: Literal["Feature"] = "Feature"
    id: Id
    geometry: Point | LineString
    properties: RouteDataProperties


class PlaceSubmissionCreate(Model):
    name: Annotated[str, Field(min_length=1, max_length=100)]
    category: Annotated[str, Field(min_length=1, max_length=100)]
    address: Annotated[str, Field(max_length=300)] | None = None
    location: Coordinates | None = None
    description: Description = ""

    @model_validator(mode="after")
    def check_text(self) -> Self:
        for field in ("name", "category"):
            value = getattr(self, field).strip()
            if not value:
                raise ValueError("Pole nie może być puste.")
            setattr(self, field, value)
        if self.address is not None:
            self.address = self.address.strip() or None
        if self.address is None and self.location is None:
            raise ValueError("Podaj adres albo współrzędne miejsca.")
        return self


class PlaceSubmissionReview(Model):
    decision: Literal["accepted", "rejected"]
    comment: Annotated[str, Field(min_length=1, max_length=4000)]
    location: Coordinates | None = None

    @model_validator(mode="after")
    def check_comment(self) -> Self:
        self.comment = self.comment.strip()
        if not self.comment:
            raise ValueError("Pole nie może być puste.")
        return self


class PlaceSubmission(PlaceSubmissionCreate):
    id: Id
    author_id: Id
    status: ReportStatus = "pending"
    created_at: AwareDatetime
    reviewed_at: AwareDatetime | None = None
    reviewer_id: Id | None = None
    review_comment: str | None = None
