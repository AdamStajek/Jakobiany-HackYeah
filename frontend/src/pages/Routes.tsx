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
} from "lucide-react";
import { useDemo } from "../state/DemoContext";
import MapView from "../components/MapView";
import Numeric from "../components/Numeric";
import { FactRow, PageHeading, Status } from "../components/Common";
import {
  getPlace,
  planRoute,
  searchRoutePoints,
  type PlannedRoute,
} from "../data/api";

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
  onSelect,
}: {
  label: string;
  onSelect: (point: {
    id: string;
    name: string;
    location: Coordinates;
  }) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<
    {
      id: string;
      name: string;
      address: string | null;
      location: Coordinates;
    }[]
  >([]);
  const [error, setError] = useState("");
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
  warnings: string[];
  origin: string;
  destination: string;
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
  const [params] = useSearchParams();
  const { constraints, setConstraints, notify, location: userLocation } = useDemo();
  const [origin, setOrigin] = useState(params.get("from") === "empty" ? "" : "rynek");
  const [destination, setDestination] = useState(params.get("to") || "wawel");
  const [originName, setOriginName] = useState("Wybrany punkt");
  const [originCoordinates, setOriginCoordinates] = useState<Coordinates | null>(
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
  ]);

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
        warnings: response.warnings,
        origin: points.find((point) => point.id === origin)?.name || originName,
        destination:
          points.find((point) => point.id === destination)?.name ||
          destinationName,
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
    mapContainer.current?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
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
    setPicking(null);
  }

  return (
    <div className="page">
      <PageHeading
        eyebrow="SPOKOJNIE, KROK PO KROKU"
        title="Znajdź swoją trasę"
        description="Wybierz cel i ustaw to, co ma znaczenie po drodze."
      />
      <div className="route-grid">
        <form className="panel route-form" onSubmit={submit}>
          <h2>Dokąd się wybierasz?</h2>
          <PointSearch
            label="Skąd"
            onSelect={(point) => {
              setOrigin(point.id);
              setOriginName(point.name);
              setOriginCoordinates(null);
            }}
          />
          <button
            type="button"
            className="button subtle full"
            onClick={() => chooseOnMap("origin")}
          >
            Wskaż początek na mapie
          </button>
          <PointSearch
            label="Dokąd"
            onSelect={(point) => {
              setDestination(point.id);
              setDestinationName(point.name);
              setDestinationCoordinates(null);
            }}
          />
          <button
            type="button"
            className="button subtle full"
            onClick={() => chooseOnMap("destination")}
          >
            Wskaż cel na mapie
          </button>
          {picking && (
            <p role="status" className="route-picking-status">
              Kliknij na mapie {picking === "origin" ? "początek" : "cel"} trasy.{" "}
              <button
                type="button"
                className="button subtle"
                onClick={() => setPicking(null)}
              >
                Anuluj wybór
              </button>
            </p>
          )}
          <button className="button primary full route-submit" disabled={loading}>
            {loading ? "Planowanie…" : "Pokaż trasę"}
            <ArrowRight size={18} />
          </button>
        </form>
        <section className="panel route-needs">
          <h2>Twoje potrzeby na trasie</h2>
          <label className="check-field">
            <input
              type="checkbox"
              checked={constraints.require_step_free_access === true}
              onChange={(event) =>
                setConstraints({
                  ...constraints,
                  require_step_free_access: event.target.checked ? true : null,
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
        <div className="route-map" ref={mapContainer}>
          <MapView
            places={noPlaces}
            route={plan?.route.geometry}
            endpoints={endpoints}
            onSelectPoint={picking ? selectMapPoint : undefined}
          />
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
                <p className="eyebrow">ZAPLANOWANA TRASA</p>
                <h2>{durationLabel(plan.route.estimated_duration_s)}</h2>
                <p>
                  {distanceLabel(plan.route.distance_m)} · {plan.origin} →{" "}
                  {plan.destination}
                </p>
                <Status assessment={plan.route.assessment} />
                <Warnings warnings={plan.warnings} />
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
      <Warnings warnings={plan.warnings} />
      <MapView places={noPlaces} route={plan.route.geometry} />
      {plan.route.segments.length === 0 && (
        <p>Jesteś już w punkcie docelowym. Trasa nie zawiera odcinków.</p>
      )}
      {plan.route.segments.map((segment, index) => (
        <article className="panel segment" key={segment.id}>
          <span className="step-number">{index + 1}</span>
          <div>
            <h2>{segment.instruction}</h2>
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
          <h1>{current?.instruction || "Jesteś w punkcie docelowym."}</h1>
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
      <MapView places={noPlaces} route={plan.route.geometry} />
      <p className="warning-box">
        Podgląd zaplanowanej trasy — bez śledzenia pozycji. Sprawdź warunki w
        terenie przed przejściem.
      </p>
      <Warnings warnings={plan.warnings} />
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
