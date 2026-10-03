import { useState, useEffect } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Route as RouteIcon,
  Check,
  Trees,
  TriangleAlert,
  ChevronLeft,
  ArrowUp,
  Plus,
  Volume2,
} from "lucide-react";
import { useDemo } from "../state/DemoContext";
import MapView from "../components/MapView";
import Numeric from "../components/Numeric";
import { PageHeading } from "../components/Common";
import { places, routeSteps } from "../data/mock";
import { NotFound } from "./Info";
export function RoutePage() {
  const [params] = useSearchParams();
  const [origin, setOrigin] = useState("Dworzec Główny");
  const [destination, setDestination] = useState(
    params.get("to") || places[0].id,
  );
  const [shown, setShown] = useState(false);
  const [planned, setPlanned] = useState({ origin, destination });
  const { constraints, setConstraints } = useDemo();
  const place = places.find((p) => p.id === planned.destination)!;
  return (
    <div className="page">
      <PageHeading
        eyebrow="SPOKOJNIE, KROK PO KROKU"
        title="Znajdź swoją trasę"
        description="Wybierz cel i ustaw to, co ma znaczenie po drodze."
      />
      <div className="route-grid">
        <form
          className="panel route-form"
          onSubmit={(e) => {
            e.preventDefault();
            setPlanned({ origin, destination });
            setShown(true);
          }}
        >
          <h2>Dokąd się wybierasz?</h2>
          <label className="field">
            Skąd
            <select
              value={origin}
              onChange={(e) => {
                setOrigin(e.target.value);
                setShown(false);
              }}
            >
              <option>Dworzec Główny</option>
              <option>Rynek Główny</option>
            </select>
          </label>
          <label className="field">
            Dokąd
            <select
              value={destination}
              onChange={(e) => {
                setDestination(e.target.value);
                setShown(false);
              }}
            >
              {places.map((p) => (
                <option value={p.id} key={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <hr />
          <h3>Twoje potrzeby na trasie</h3>
          <label className="check-field">
            <input
              type="checkbox"
              checked={constraints.require_step_free_access === true}
              onChange={(e) =>
                setConstraints({
                  ...constraints,
                  require_step_free_access: e.target.checked ? true : null,
                  max_steps: e.target.checked ? 0 : null,
                })
              }
            />
            Unikaj schodów
          </label>
          <Numeric
            label="Maksymalne nachylenie (%)"
            value={constraints.max_slope_percent}
            onChange={(v) =>
              setConstraints({ ...constraints, max_slope_percent: v })
            }
          />
          <Numeric
            label="Odpoczynek co (m)"
            min={1}
            value={constraints.max_distance_without_rest_m}
            onChange={(v) =>
              setConstraints({ ...constraints, max_distance_without_rest_m: v })
            }
          />
          <button className="button primary full">
            Pokaż trasę <ArrowRight size={18} />
          </button>
          <p className="muted small">
            Przykładowy wariant, bez pobierania lokalizacji.
          </p>
        </form>
        <div className="route-map">
          <MapView places={[]} route={shown} />
        </div>
        {shown ? (
          <aside className="panel route-summary" aria-live="polite">
            <p className="eyebrow">PRZYKŁADOWA TRASA</p>
            <h2>
              18 <span>minut</span>
            </h2>
            <p>
              1,2 km · {planned.origin} → {place.name}
            </p>
            <span className="status warning">
              <TriangleAlert size={17} />
              Trasa niepewna
            </span>
            <p className="muted">
              Podgląd stałego scenariusza — wybór celu i potrzeb nie oblicza
              nowej trasy.
            </p>
            <ul className="route-facts">
              <li>
                <Check />
                Brak stopni na potwierdzonych odcinkach
              </li>
              <li>
                <Check />
                Nachylenie do 4% na znanych odcinkach
              </li>
              <li>
                <Trees />
                Miejsca odpoczynku przy Plantach
              </li>
            </ul>
            <div className="warning-box">
              Na 150 m nie potwierdzono nawierzchni. Dopasowanie do Twoich
              potrzeb wymaga weryfikacji.
            </div>
            <Link className="button subtle full" to="/route/demo/details">
              Szczegóły trasy
            </Link>
            <Link className="button primary full" to="/navigation?route=demo">
              Uruchom podgląd nawigacji
            </Link>
          </aside>
        ) : (
          <aside className="panel route-summary">
            <RouteIcon size={38} />
            <h2>Droga dopasowana do Ciebie</h2>
            <p>
              Wypełnij pola i zobacz przykładowy wariant trasy oraz informacje o
              odcinkach.
            </p>
          </aside>
        )}
      </div>
    </div>
  );
}
export function RouteDetails() {
  const { id } = useParams();
  if (id !== "demo") return <NotFound />;
  return (
    <div className="page narrow">
      <Link className="back-link" to="/route">
        <ChevronLeft size={18} />
        Planowanie trasy
      </Link>
      <PageHeading
        title="Szczegóły przykładowej trasy"
        description="1,2 km · około 18 minut · dane demonstracyjne"
      />
      <div className="warning-box">
        Trasa niepewna: brak potwierdzonej nawierzchni na części Plant.
      </div>
      {routeSteps.map((s, i) => (
        <article className="panel segment" key={s.street}>
          <span className="step-number">{i + 1}</span>
          <div>
            <h2>{s.street}</h2>
            <p>{s.instruction}</p>
            <p>
              {s.distance} m · {s.surface} · nachylenie {s.slope}%
            </p>
            <p>
              <Trees size={17} /> {s.rest}
            </p>
            <small>
              Przykładowe potwierdzenie użytkownika · 02.10.2026 · wiarygodność
              88%
            </small>
            {s.warning && (
              <p className="warning-box">
                {s.warning} Brak źródła i oceny wiarygodności.
              </p>
            )}
          </div>
        </article>
      ))}
      <Link className="button primary" to="/navigation?route=demo">
        Podgląd nawigacji
      </Link>
    </div>
  );
}
export function Navigation() {
  const [step, setStep] = useState(0);
  const [large, setLarge] = useState(false);
  const { notify } = useDemo();
  useEffect(
    () => () => {
      window.speechSynthesis?.cancel();
    },
    [],
  );
  function speak() {
    if (!("speechSynthesis" in window)) {
      notify("Odczyt głosowy jest niedostępny w tej przeglądarce.");
      return;
    }
    const u = new SpeechSynthesisUtterance(routeSteps[step].instruction);
    u.lang = "pl-PL";
    window.speechSynthesis.speak(u);
  }
  return (
    <div className="page navigation-page">
      <div className={`navigation-instruction ${large ? "large" : ""}`}>
        <ArrowUp size={54} />
        <div>
          <p>Podgląd kroku {step + 1} z 3</p>
          <h1>{routeSteps[step].instruction}</h1>
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
      <MapView places={[]} route />
      <div className="warning-box">
        Symulacja — bez śledzenia pozycji.{" "}
        {routeSteps[step].warning ||
          "Sprawdź warunki w terenie przed przejściem."}
      </div>
      <div className="navigation-footer">
        <strong>
          {Math.ceil(
            (routeSteps.slice(step).reduce((sum, s) => sum + s.distance, 0) /
              1200) *
              18,
          )}{" "}
          min <small>do końca przykładowej trasy</small>
        </strong>
        <button
          className="button subtle"
          disabled={step === 0}
          onClick={() => setStep((s) => s - 1)}
        >
          Poprzedni krok
        </button>
        {step < 2 ? (
          <button
            className="button primary"
            onClick={() => setStep((s) => s + 1)}
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
