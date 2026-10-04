import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  Link,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowRight,
  ChevronLeft,
  ArrowUp,
  Plus,
  Volume2,
  Bus,
  Footprints,
  Car,
} from "lucide-react";
import { useDemo } from "../state/DemoContext";
import MapView from "../components/MapView";
import Numeric from "../components/Numeric";
import AISearch from "../components/AISearch";
import ProfileSettingsButton from "../components/ProfileSettingsButton";
import { FactRow, PageHeading, Status } from "../components/Common";
import {
  getPlace,
  planRoute,
  searchRoutePoints,
  getMobilityMap,
  type MobilityPoint,
  type TravelMode,
  type PlannedRoute,
} from "../data/api";
import type { Source } from "../data/types";

// Quick choices; any catalogue place or point selected on the map is supported.
const points = [
  { id: "rynek", name: "Rynek Główny" },
  { id: "planty", name: "Planty" },
  { id: "wawel", name: "Wawel" },
];
const noPlaces: [] = [];
type Coordinates = { lat: number; lon: number };
function PointSearch({
  label,
  initialQuery = "",
  onSelect,
}: {
  label: string;
  initialQuery?: string;
  onSelect: (point: {
    id: string;
    name: string;
    location: Coordinates;
  }) => void;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<
    {
      id: string;
      name: string;
      address: string | null;
      location: Coordinates;
    }[]
  >([]);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    setResults([]);
    setError("");
    if (query.trim().length < 2) return;
    const timer = setTimeout(
      () =>
        searchRoutePoints(query.trim(), controller.signal)
          .then((page) => {
            if (!controller.signal.aborted) setResults(page.items);
          })
          .catch(() => {
            if (!controller.signal.aborted)
              setError(
                "Nie udało się wyszukać miejsc. Możesz wskazać punkt na mapie.",
              );
          }),
      250,
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);
  return (
    <div className="route-point-search">
      <label className="field">
        {label}
        <input
          ref={input}
          value={query}
          placeholder="Nazwa miejsca lub adres"
          onChange={(event) => setQuery(event.target.value)}
          autoComplete="off"
        />
      </label>
      {error && (
        <p role="status" className="small">
          {error}
        </p>
      )}
      {results.length > 0 && (
        <ul className="route-point-results" aria-label={`Wyniki: ${label}`}>
          {results.map((point) => (
            <li key={point.id}>
              <button
                type="button"
                onClick={() => {
                  onSelect(point);
                  setQuery("");
                  setResults([]);
                  input.current?.focus();
                }}
              >
                <strong>{point.name}</strong>
                <small>{point.address}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
type SavedPlan = {
  route: PlannedRoute;
  alternatives?: PlannedRoute[];
  warnings: string[];
  origin: string;
  destination: string;
  attribution?: Source[];
};
const storageKey = "swoja-droga-route";
function readPlan(): SavedPlan | null {
  try {
    const plan = JSON.parse(
      sessionStorage.getItem(storageKey) || "null",
    ) as SavedPlan | null;
    return plan &&
      typeof plan.route?.id === "string" &&
      plan.route.geometry?.type === "LineString" &&
      Array.isArray(plan.route.segments) &&
      Array.isArray(plan.warnings)
      ? plan
      : null;
  } catch {
    return null;
  }
}
function distanceLabel(meters: number) {
  return meters < 1000
    ? `${Math.round(meters)} m`
    : `${(meters / 1000).toLocaleString("pl-PL", { maximumFractionDigits: 2 })} km`;
}
function durationLabel(seconds: number | null) {
  return seconds === null ? "Czas nieznany" : `${Math.ceil(seconds / 60)} min`;
}
const modeLabels = {
  walk: "Pieszo",
  transit: "Komunikacja miejska",
  car: "Samochód",
};
function timeLabel(value: string) {
  return new Date(value).toLocaleTimeString("pl-PL", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Warsaw",
  });
}
function TransitTime({
  segment,
}: {
  segment?: PlannedRoute["segments"][number];
}) {
  if (segment?.mode !== "transit" || !segment.departure_at) return null;
  return (
    <p className="transit-time">
      <Bus size={18} aria-hidden="true" /> {timeLabel(segment.departure_at)}
      {segment.arrival_at && ` → ${timeLabel(segment.arrival_at)}`}
      {segment.delay_s == null
        ? " · Według rozkładu"
        : segment.delay_s > 0
          ? ` · Opóźnienie ${Math.ceil(segment.delay_s / 60)} min`
          : segment.delay_s < 0
            ? ` · ${Math.ceil(-segment.delay_s / 60)} min przed rozkładem`
            : " · Dane bieżące: punktualnie"}
    </p>
  );
}
function RouteSources({ plan }: { plan: SavedPlan }) {
  return (
    <p className="small route-sources">
      {plan.attribution
        ?.filter((s) => s.url)
        .map((s, i) => (
          <span key={s.url}>
            {i > 0 && " · "}
            <a href={s.url!} target="_blank" rel="noreferrer">
              {s.label}
            </a>
          </span>
        ))}
    </p>
  );
}
function planEndpoints(plan: SavedPlan) {
  const coordinates = plan.route.geometry.coordinates;
  if (!coordinates.length) return [];
  return [
    { coordinates: coordinates[0], label: `Start: ${plan.origin}` },
    { coordinates: coordinates[coordinates.length - 1], label: `Cel: ${plan.destination}` },
  ].map(({ coordinates: [lon, lat], label }) => ({ lat, lon, label }));
}
function routeMarkers(route: PlannedRoute): MobilityPoint[] {
  const stops = route.segments
    .filter((s) => s.mode === "transit")
    .flatMap((s) => [
      {
        id: `${s.id}-start`,
        name: s.from_stop || "Przystanek początkowy",
        coordinates: s.geometry.coordinates[0],
      },
      {
        id: `${s.id}-end`,
        name: s.to_stop || "Przystanek końcowy",
        coordinates: s.geometry.coordinates.at(-1)!,
      },
    ])
    .map((p) => ({
      id: p.id,
      name: p.name,
      kind: "stop" as const,
      location: { lon: p.coordinates[0], lat: p.coordinates[1] },
      line: null,
      updated_at: null,
    }));
  return [...stops, ...(route.parking ? [route.parking] : [])];
}
function Warnings({ warnings }: { warnings: string[] }) {
  return (
    <>
      {warnings.map((warning, i) => (
        <p className="warning-box" key={i}>
          {warning}
        </p>
      ))}
    </>
  );
}
function RouteNotes({ warnings }: { warnings: string[] }) {
  return (
    <>
      {warnings.map((warning, i) => (
        <p className="route-note" key={i}>
          {warning}
        </p>
      ))}
    </>
  );
}
function MissingRoute() {
  return (
    <div className="page narrow">
      <PageHeading
        title="Brak zaplanowanej trasy"
        description="Zaplanuj trasę, aby zobaczyć jej szczegóły i instrukcje."
      />
      <Link className="button primary" to="/route">
        Planowanie trasy
      </Link>
    </div>
  );
}

export function RoutePage() {
  const [aiPoints, setAiPoints] = useState({
    origin: "",
    destination: "",
    revision: 0,
  });
  const [params] = useSearchParams();
  const {
    constraints,
    setConstraints,
    notify,
    location: userLocation,
  } = useDemo();
  const [origin, setOrigin] = useState(
    params.get("from") === "empty" ? "" : "rynek",
  );
  const [destination, setDestination] = useState(params.get("to") || "wawel");
  const [originName, setOriginName] = useState("Wybrany punkt");
  const [originCoordinates, setOriginCoordinates] =
    useState<Coordinates | null>(
      params.get("from") === "location" ? userLocation : null,
    );
  const [destinationCoordinates, setDestinationCoordinates] =
    useState<Coordinates | null>(null);
  const [picking, setPicking] = useState<"origin" | "destination" | null>(null);
  const mapContainer = useRef<HTMLDivElement>(null);
  const [destinationName, setDestinationName] = useState("Wybrane miejsce");
  const [plan, setPlan] = useState<SavedPlan | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<TravelMode>("walk");
  const [accessibleParking, setAccessibleParking] = useState(false);
  const [departureAt, setDepartureAt] = useState("");
  const [mobility, setMobility] = useState<MobilityPoint[]>([]);
  const [vehicles, setVehicles] = useState<MobilityPoint[]>([]);
  const [autoUpdateVehicles, setAutoUpdateVehicles] = useState(true);
  const [mapWarnings, setMapWarnings] = useState<string[]>([]);
  const [vehicleWarnings, setVehicleWarnings] = useState<string[]>([]);
  const [mapSources, setMapSources] = useState<Source[]>([]);
  const request = useRef<AbortController | null>(null);
  const endpoints = useMemo(
    () => [
      ...(originCoordinates
        ? [{ ...originCoordinates, label: "Początek trasy" }]
        : []),
      ...(destinationCoordinates
        ? [{ ...destinationCoordinates, label: "Cel trasy" }]
        : []),
    ],
    [originCoordinates, destinationCoordinates],
  );
  const knownDestination = points.some((point) => point.id === destination);

  useEffect(() => {
    setPlan(null);
    setWarnings([]);
    setError(null);
    setLoading(false);
    request.current?.abort();
    return () => request.current?.abort();
  }, [
    origin,
    destination,
    originCoordinates,
    destinationCoordinates,
    constraints,
    mode,
    accessibleParking,
    departureAt,
  ]);

  useEffect(() => {
    const controller = new AbortController();
    setMobility([]);
    setMapWarnings([]);
    setMapSources([]);
    if (mode === "walk" || (mode === "car" && !accessibleParking)) return;
    getMobilityMap(mode === "transit" ? "stops" : "parking", controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setMobility(result.items);
          setMapWarnings(result.warnings);
          setMapSources(result.attribution);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setMapWarnings([
            "Nie udało się pobrać przystanków lub parkingów na mapę.",
          ]);
      });
    return () => controller.abort();
  }, [mode, accessibleParking]);

  useEffect(() => {
    if (mode !== "transit") {
      setVehicles([]);
      setVehicleWarnings([]);
      return;
    }
    if (!autoUpdateVehicles) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const result = await getMobilityMap("vehicles", controller.signal);
        if (!controller.signal.aborted) {
          setVehicles(result.items);
          setVehicleWarnings(result.warnings);
        }
      } catch {
        if (!controller.signal.aborted) {
          setVehicles([]);
          setVehicleWarnings(["Pozycje pojazdów są chwilowo niedostępne."]);
        }
      }
      if (!controller.signal.aborted) timer = setTimeout(refresh, 30000);
    }
    void refresh();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [mode, autoUpdateVehicles]);

  useEffect(() => {
    const target = params.get("to");
    const from = params.get("from");
    setDestination(target || "wawel");
    setDestinationCoordinates(null);
    if (from === "location" && userLocation) {
      setOrigin("current-location");
      setOriginName("Twoja lokalizacja");
      setOriginCoordinates(userLocation);
    } else if (from === "location") {
      setOrigin("");
      setOriginName("Wybierz początek");
      setOriginCoordinates(null);
    } else if (from === "empty") {
      setOrigin("");
      setOriginName("Wybierz początek");
      setOriginCoordinates(null);
    }
  }, [params]);

  useEffect(() => {
    if (knownDestination || destinationCoordinates) return;
    let cancelled = false;
    setDestinationName("Wybrane miejsce");
    getPlace(destination)
      .then((place) => {
        if (!cancelled) setDestinationName(place.name);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [destination, knownDestination, destinationCoordinates]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (
      (!origin && !originCoordinates) ||
      (!destination && !destinationCoordinates)
    ) {
      setError(
        "Wybierz początek i cel trasy z wyników wyszukiwania lub na mapie.",
      );
      return;
    }
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setPlan(null);
    setWarnings([]);
    setError(null);
    try {
      const response = await planRoute(
        originCoordinates || origin,
        destinationCoordinates || destination,
        constraints,
        controller.signal,
        {
          mode,
          accessible_parking: mode === "car" && accessibleParking,
          ...(mode === "transit" && departureAt
            ? { departure_at: new Date(departureAt).toISOString() }
            : {}),
        },
      );
      if (controller.signal.aborted) return;
      setWarnings(response.warnings);
      const route = response.routes[0];
      if (!route) {
        setError("Nie znaleziono trasy spełniającej Twoje wymagania.");
        return;
      }
      const result = {
        route,
        alternatives: response.routes,
        warnings: response.warnings,
        origin: points.find((point) => point.id === origin)?.name || originName,
        destination:
          points.find((point) => point.id === destination)?.name ||
          destinationName,
        attribution: response.attribution,
      };
      setPlan(result);
      try {
        sessionStorage.setItem(storageKey, JSON.stringify(result));
      } catch {
        notify(
          "Trasa jest dostępna do zamknięcia tego widoku; przeglądarka nie pozwala jej zachować po odświeżeniu.",
        );
      }
    } catch (failure) {
      if (!controller.signal.aborted)
        setError(
          failure instanceof Error
            ? failure.message
            : "Nie udało się zaplanować trasy.",
        );
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  function chooseOnMap(which: "origin" | "destination") {
    setPicking(which);
    requestAnimationFrame(() =>
      mapContainer.current?.querySelector<HTMLElement>(".map-canvas")?.focus(),
    );
  }
  function finishPicking() {
    setPicking(null);
    document.getElementById(`pick-${picking}`)?.focus();
  }
  function selectMapPoint(point: Coordinates) {
    const name = `${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}`;
    if (picking === "origin") {
      setOrigin("map-origin");
      setOriginName(name);
      setOriginCoordinates(point);
    } else {
      setDestination("map-destination");
      setDestinationName(name);
      setDestinationCoordinates(point);
    }
    finishPicking();
  }

  return (
    <div className="page">
      <PageHeading
        eyebrow="SPOKOJNIE, KROK PO KROKU"
        title="Znajdź swoją trasę"
        description="Wybierz cel i ustaw to, co ma znaczenie po drodze."
      />
      <div className="route-grid">
        {mode !== "car" && (
          <section className="panel route-needs">
            <h2>Twoje potrzeby na trasie</h2>
            <label className="check-field route-mobility-choice">
              <input
                type="checkbox"
                checked={
                  constraints.require_step_free_access === true &&
                  constraints.max_steps === 0 &&
                  constraints.max_slope_percent !== null &&
                  constraints.max_slope_percent <= 5
                }
                onChange={(event) =>
                  setConstraints({
                    ...constraints,
                    require_step_free_access: event.target.checked
                      ? true
                      : null,
                    max_steps: event.target.checked ? 0 : null,
                    max_slope_percent: event.target.checked
                      ? Math.min(constraints.max_slope_percent ?? 5, 5)
                      : null,
                  })
                }
              />
              <span className="route-mobility-copy">
                <span>Poruszam się o kulach lub na wózku</span>
                <span className="small">
                  Automatycznie unikaj schodów i nachyleń powyżej 5%.
                </span>
              </span>
            </label>
            <label className="check-field">
              <input
                type="checkbox"
                checked={constraints.require_step_free_access === true}
                onChange={(event) =>
                  setConstraints({
                    ...constraints,
                    require_step_free_access: event.target.checked
                      ? true
                      : null,
                    max_steps: event.target.checked ? 0 : null,
                  })
                }
              />
              Unikaj schodów
            </label>
            <label className="check-field">
              <input
                type="checkbox"
                checked={constraints.allowed_surfaces !== null}
                onChange={(event) =>
                  setConstraints({
                    ...constraints,
                    allowed_surfaces: event.target.checked
                      ? ["paved", "asphalt"]
                      : null,
                  })
                }
              />
              Utwardzona nawierzchnia
            </label>
            <Numeric
              label="Maks. nachylenie (%)"
              value={constraints.max_slope_percent}
              onChange={(value) =>
                setConstraints({ ...constraints, max_slope_percent: value })
              }
            />
            <Numeric
              label="Odpoczynek co (m)"
              min={1}
              value={constraints.max_distance_without_rest_m}
              onChange={(value) =>
                setConstraints({
                  ...constraints,
                  max_distance_without_rest_m: value,
                })
              }
            />
          </section>
        )}
        <form className="panel route-form" onSubmit={submit}>
          <h2>Dokąd się wybierasz?</h2>
          <fieldset className="route-modes">
            <legend>Sposób podróży</legend>
            {(
              [
                { mode: "walk", icon: Footprints },
                { mode: "transit", icon: Bus },
                { mode: "car", icon: Car },
              ] as const
            ).map(({ mode: value, icon: Icon }) => (
              <button
                key={value}
                type="button"
                aria-pressed={mode === value}
                aria-label={modeLabels[value]}
                onClick={() => setMode(value)}
              >
                <Icon size={23} aria-hidden="true" />
                <span>{modeLabels[value]}</span>
              </button>
            ))}
          </fieldset>
          {mode === "car" && (
            <label className="check-field route-parking-choice">
              <input
                type="checkbox"
                checked={accessibleParking}
                onChange={(event) => setAccessibleParking(event.target.checked)}
              />
              Prowadź do miejsca parkingowego dla osób z niepełnosprawnościami
            </label>
          )}
          {mode === "transit" && (
            <>
              <label className="field route-departure">
                <span id="departure-label">Wyjazd</span>
                <input
                  aria-labelledby="departure-label"
                  aria-describedby="departure-help"
                  type="datetime-local"
                  value={departureAt}
                  onChange={(event) => setDepartureAt(event.target.value)}
                />
                <small id="departure-help">
                  Puste pole oznacza wyjazd teraz.
                </small>
              </label>
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={autoUpdateVehicles}
                  onChange={(event) =>
                    setAutoUpdateVehicles(event.target.checked)
                  }
                />
                Automatycznie aktualizuj pozycje pojazdów (co 30 s)
              </label>
            </>
          )}
          <div className="profile-settings-control">
            <ProfileSettingsButton />
          </div>
          <AISearch
            mode="routes"
            onApply={(proposal) => {
              setAiPoints((current) => ({
                origin: proposal.origin_query || "",
                destination: proposal.destination_query || "",
                revision: current.revision + 1,
              }));
              if (proposal.origin_query) {
                setOrigin("");
                setOriginCoordinates(null);
              }
              if (proposal.destination_query) {
                setDestination("");
                setDestinationCoordinates(null);
              }
            }}
          />
          <PointSearch
            key={`origin-${aiPoints.revision}`}
            initialQuery={aiPoints.origin}
            label="Skąd"
            onSelect={(point) => {
              setOrigin(point.id);
              setOriginName(point.name);
              setOriginCoordinates(null);
            }}
          />
          <button
            id="pick-origin"
            type="button"
            className="button subtle full"
            aria-pressed={picking === "origin"}
            onClick={() => chooseOnMap("origin")}
          >
            Wskaż początek na mapie
          </button>
          <p role="status" className="small route-selected-point">
            Skąd:{" "}
            {points.find((p) => p.id === origin)?.name ||
              (origin || originCoordinates ? originName : "Wybierz punkt")}
          </p>
          <PointSearch
            key={`destination-${aiPoints.revision}`}
            initialQuery={aiPoints.destination}
            label="Dokąd"
            onSelect={(point) => {
              setDestination(point.id);
              setDestinationName(point.name);
              setDestinationCoordinates(null);
            }}
          />
          <button
            id="pick-destination"
            type="button"
            className="button subtle full"
            aria-pressed={picking === "destination"}
            onClick={() => chooseOnMap("destination")}
          >
            Wskaż cel na mapie
          </button>
          <p role="status" className="small route-selected-point">
            Dokąd:{" "}
            {points.find((p) => p.id === destination)?.name ||
              (destination || destinationCoordinates
                ? destinationName
                : "Wybierz punkt")}
          </p>
          {picking && (
            <p role="status" className="route-picking-status">
              Wybierz {picking === "origin" ? "początek" : "cel"} trasy
              kliknięciem na mapie lub przesuń mapę strzałkami i naciśnij Enter.{" "}
              <button
                type="button"
                className="button subtle"
                onClick={finishPicking}
              >
                Anuluj wybór
              </button>
            </p>
          )}
          <button
            className="button primary full route-submit"
            disabled={loading}
          >
            {loading ? "Planowanie…" : "Pokaż trasę"}
            <ArrowRight size={18} />
          </button>
        </form>
        <div className="route-map" ref={mapContainer}>
          <MapView
            places={noPlaces}
            route={plan?.route.geometry}
            routeVariants={plan?.alternatives}
            segments={plan?.route.segments}
            mobility={[
              ...mobility,
              ...vehicles,
              ...(plan?.route.parking &&
              !mobility.some((p) => p.id === plan.route.parking?.id)
                ? [plan.route.parking]
                : []),
            ]}
            endpoints={plan ? planEndpoints(plan) : endpoints}
            onSelectPoint={picking ? selectMapPoint : undefined}
            onCancelSelection={finishPicking}
          />
          {mode === "transit" && (
            <p className="small route-map-legend">
              ● Przystanki · 🚌 Bieżące pozycje pojazdów · Zielona trasa:
              komunikacja · Niebieska: dojście piesze
            </p>
          )}
          {mode === "car" && accessibleParking && (
            <p className="small route-map-legend">
              P ♿ Miejskie miejsca postojowe OZN — bez informacji o zajętości.
            </p>
          )}
          <Warnings warnings={[...mapWarnings, ...vehicleWarnings]} />
          <p className="small route-sources">
            {mapSources.map(
              (s) =>
                s.url && (
                  <a key={s.url} href={s.url} target="_blank" rel="noreferrer">
                    {s.label}
                  </a>
                ),
            )}
          </p>
        </div>
        {loading || plan || error ? (
          <aside
            className="panel route-summary"
            aria-live="polite"
            aria-busy={loading}
          >
            {loading ? (
              <p>Obliczamy trasę z uwzględnieniem Twoich potrzeb…</p>
            ) : plan ? (
              <>
                {plan.route.mode !== "car" && plan.route.mode !== "transit" && (
                  <div aria-label="Warianty trasy pieszej">
                    {[...(plan.alternatives || [])]
                      .sort(
                        (a, b) =>
                          Number(b.variant === "fastest") -
                          Number(a.variant === "fastest"),
                      )
                      .map((route) => (
                        <div key={route.id}>
                          <button
                            type="button"
                            className="button subtle full"
                            aria-pressed={plan.route.id === route.id}
                            onClick={() => {
                              const selected = { ...plan, route };
                              setPlan(selected);
                              try {
                                sessionStorage.setItem(
                                  storageKey,
                                  JSON.stringify(selected),
                                );
                              } catch {
                                notify(
                                  "Nie udało się zachować wybranej trasy po odświeżeniu.",
                                );
                              }
                            }}
                          >
                            {route.variant === "fastest"
                              ? "Najszybsza trasa"
                              : "Trasa z uwzględnieniem ograniczeń"}
                            {" · "}
                            {durationLabel(route.estimated_duration_s)}
                            {" · "}
                            {distanceLabel(route.distance_m)}
                          </button>
                          <p>{route.assessment.summary}</p>
                        </div>
                      ))}
                    {plan.alternatives?.some(
                      (route) => route.variant === "fastest",
                    ) &&
                      !plan.alternatives.some(
                        (route) => route.variant === "constrained",
                      ) && (
                        <p className="warning-box">
                          Nie znaleziono trasy uwzględniającej wybrane
                          ograniczenia.
                        </p>
                      )}
                    {plan.alternatives?.length === 2 &&
                      JSON.stringify(plan.alternatives[0].geometry) ===
                        JSON.stringify(plan.alternatives[1].geometry) && (
                        <p>Oba warianty prowadzą tą samą drogą.</p>
                      )}
                  </div>
                )}
                <p className="eyebrow">ZAPLANOWANA TRASA</p>
                <h2>{durationLabel(plan.route.estimated_duration_s)}</h2>
                <p>
                  {distanceLabel(plan.route.distance_m)} · {plan.origin} →{" "}
                  {plan.destination}
                </p>
                <p>
                  {modeLabels[plan.route.mode || "walk"]}
                  {plan.route.parking &&
                    ` · Parking: ${plan.route.parking.name}`}
                </p>
                {plan.route.segments
                  .filter((s) => s.mode === "transit")
                  .map((s) => (
                    <div key={s.id}>
                      <strong>
                        Linia {s.line}: {s.from_stop} → {s.to_stop}
                      </strong>
                      <TransitTime segment={s} />
                    </div>
                  ))}
                <details className="route-steps-preview">
                  <summary>Krok po kroku · {plan.route.segments.length} odcinków</summary>
                  <ol>
                    {plan.route.segments.map((segment) => (
                      <li key={segment.id}>
                        {segment.instruction} <strong>{distanceLabel(segment.distance_m)}</strong>
                      </li>
                    ))}
                  </ol>
                </details>
                <Status assessment={plan.route.assessment} />
                <RouteNotes warnings={plan.warnings} />
                <RouteSources plan={plan} />
                <Link
                  className="button subtle full"
                  to={`/route/${encodeURIComponent(plan.route.id)}/details`}
                  state={plan}
                >
                  Szczegóły trasy
                </Link>
                <Link
                  className="button primary full"
                  to={`/navigation?route=${encodeURIComponent(plan.route.id)}`}
                  state={plan}
                >
                  Uruchom podgląd nawigacji
                </Link>
              </>
            ) : (
              <>
                <h2>Nie udało się wyznaczyć trasy</h2>
                <p role="alert">{error}</p>
                <Warnings warnings={warnings} />
              </>
            )}
          </aside>
        ) : null}
      </div>
    </div>
  );
}

export function RouteDetails() {
  const { id } = useParams();
  const location = useLocation();
  const plan = (location.state as SavedPlan | null) || readPlan();
  if (!plan || plan.route.id !== id) return <MissingRoute />;
  return (
    <div className="page narrow">
      <Link className="back-link" to="/route">
        <ChevronLeft size={18} />
        Planowanie trasy
      </Link>
      <PageHeading
        title="Szczegóły trasy"
        description={`${plan.origin} → ${plan.destination} · ${distanceLabel(plan.route.distance_m)} · ${durationLabel(plan.route.estimated_duration_s)}`}
      />
      <RouteNotes warnings={plan.warnings} />
      <RouteSources plan={plan} />
      <MapView
        places={noPlaces}
        route={plan.route.geometry}
        segments={plan.route.segments}
        mobility={routeMarkers(plan.route)}
        endpoints={planEndpoints(plan)}
      />
      {plan.route.segments.length === 0 && (
        <p>Jesteś już w punkcie docelowym. Trasa nie zawiera odcinków.</p>
      )}
      {plan.route.segments.map((segment, index) => (
        <article className="panel segment" key={segment.id}>
          <span className="step-number">{index + 1}</span>
          <div>
            <h2>{segment.instruction}</h2>
            <TransitTime segment={segment} />
            <p>{distanceLabel(segment.distance_m)}</p>
            <Status assessment={segment.assessment} />
            {segment.facts.map((fact) => (
              <FactRow key={fact.id} fact={fact} />
            ))}
            {segment.rest_points.map((rest) => (
              <p key={rest.id}>{rest.description}</p>
            ))}
            {segment.barriers.map((barrier) => (
              <p className="warning-box" key={barrier.id}>
                {barrier.description}
              </p>
            ))}
            {(segment.temporary_difficulties || []).map((difficulty) => (
              <p className="warning-box" key={difficulty.id}>
                {difficulty.description}
              </p>
            ))}
          </div>
        </article>
      ))}
      <Link
        className="button primary"
        to={`/navigation?route=${encodeURIComponent(plan.route.id)}`}
        state={plan}
      >
        Podgląd nawigacji
      </Link>
    </div>
  );
}

export function Navigation() {
  const [params] = useSearchParams();
  const location = useLocation();
  const plan = (location.state as SavedPlan | null) || readPlan();
  const [step, setStep] = useState(0);
  const [large, setLarge] = useState(false);
  const { notify } = useDemo();
  useEffect(
    () => () => {
      window.speechSynthesis?.cancel();
    },
    [],
  );
  if (!plan || plan.route.id !== params.get("route")) return <MissingRoute />;
  const segments = plan.route.segments;
  const current = segments[step];
  function speak() {
    if (!("speechSynthesis" in window)) {
      notify("Odczyt głosowy jest niedostępny w tej przeglądarce.");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(
      current?.instruction || "Jesteś w punkcie docelowym.",
    );
    utterance.lang = "pl-PL";
    window.speechSynthesis.speak(utterance);
  }
  const remainingDistance = segments
    .slice(step)
    .reduce((sum, segment) => sum + segment.distance_m, 0);
  const remainingSeconds =
    plan.route.estimated_duration_s === null
      ? null
      : plan.route.distance_m > 0
        ? (plan.route.estimated_duration_s * remainingDistance) /
          plan.route.distance_m
        : 0;
  return (
    <div className="page navigation-page">
      <div className={`navigation-instruction ${large ? "large" : ""}`}>
        <ArrowUp size={54} />
        <div>
          <p>
            {current
              ? `Podgląd kroku ${step + 1} z ${segments.length}`
              : "Cel osiągnięty"}
          </p>
          <h1 aria-live="polite" aria-atomic="true">
            {current?.instruction || "Jesteś w punkcie docelowym."}
          </h1>
        </div>
        <button
          className="icon-button"
          onClick={speak}
          aria-label="Odczytaj instrukcję"
        >
          <Volume2 />
        </button>
        <button
          className="icon-button"
          onClick={() => setLarge(!large)}
          aria-label="Powiększ instrukcję"
          aria-pressed={large}
        >
          <Plus />
        </button>
      </div>
      <TransitTime segment={current} />
      <MapView
        places={noPlaces}
        route={plan.route.geometry}
        segments={plan.route.segments}
        mobility={routeMarkers(plan.route)}
        endpoints={planEndpoints(plan)}
      />
      <p className="route-note">
        Podgląd zaplanowanej trasy — bez śledzenia pozycji. Sprawdź warunki w
        terenie przed podróżą.
      </p>
      <RouteNotes warnings={plan.warnings} />
      {(current?.temporary_difficulties || []).map((difficulty) => (
        <p className="warning-box" key={difficulty.id}>
          {difficulty.description}
        </p>
      ))}
      <div className="navigation-footer">
        <strong>
          {durationLabel(remainingSeconds)}{" "}
          <small>
            szacunkowo do końca trasy · {distanceLabel(remainingDistance)}
          </small>
        </strong>
        <button
          className="button subtle"
          disabled={step === 0}
          onClick={() => {
            window.speechSynthesis?.cancel();
            setStep(step - 1);
          }}
        >
          Poprzedni krok
        </button>
        {step < segments.length - 1 ? (
          <button
            className="button primary"
            onClick={() => {
              window.speechSynthesis?.cancel();
              setStep(step + 1);
            }}
          >
            Następny krok
          </button>
        ) : (
          <Link className="button primary" to="/route">
            Gotowe
          </Link>
        )}
        <Link className="button subtle" to="/route">
          Zakończ
        </Link>
      </div>
    </div>
  );
}
