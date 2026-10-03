import { useEffect, useState, type FormEvent } from "react";
import {
  Link,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowRight,
  TriangleAlert,
  Check,
  ShieldCheck,
  ChevronLeft,
  ClipboardCheck,
} from "lucide-react";
import { useDemo } from "../state/DemoContext";
import { PageHeading, FactRow } from "../components/Common";
import { MetricInput } from "../components/MetricInput";
import { labels } from "../data/mock";
import {
  createReport,
  getPlace,
  getMission,
  getReport,
  requestVerificationMission,
  searchPlaces,
  withPhoto,
} from "../data/api";
import {
  emptyConstraints,
  type Place,
  type PlaceSummary,
  type Report,
  type Fact,
} from "../data/types";
import type { Mission } from "../data/api";

export const reportStatus = {
  pending: "Oczekuje na weryfikację",
  accepted: "Zaakceptowano",
  rejected: "Odrzucono",
};
export function ReportHub() {
  return (
    <div className="page narrow">
      <PageHeading
        eyebrow="MAŁY GEST, DUŻA POMOC"
        title="Zgłoś"
        description="Zgłoś zauważony problem albo poproś o sprawdzenie niepewnej informacji."
      />
      <div className="report-options">
        <Link className="panel" to="/report/problem">
          <span className="option-icon warning">
            <TriangleAlert />
          </span>
          <h2>Zgłoś problem</h2>
          <p>Niedziałający podjazd, remont lub błędna informacja.</p>
          <span className="button subtle">
            Zgłoś <ArrowRight size={18} />
          </span>
        </Link>
        <Link className="panel" to="/report/verify">
          <span className="option-icon good">
            <ClipboardCheck />
          </span>
          <h2>Poproś o weryfikację</h2>
          <p>
            Wskaż miejsce i informację o dostępności, której pewność jest niska.
          </p>
          <span className="button subtle">
            Wybierz informację <ArrowRight size={18} />
          </span>
        </Link>
      </div>
      <div className="callout">
        <ShieldCheck />
        <p>
          Zgłoszenia i zdjęcia trafiają do moderatora. Dane nie zmieniają się
          przed weryfikacją.
        </p>
      </div>
    </div>
  );
}

const needsVerification = (fact: Fact) =>
  fact.status === "unconfirmed" ||
  (fact.confidence_percent !== null && fact.confidence_percent <= 60);

export function VerificationRequestForm() {
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { session } = useDemo();
  const [placeId, setPlaceId] = useState(params.get("place") || "");
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<PlaceSummary[]>([]);
  const [place, setPlace] = useState<Place | null>(null);
  const [factIds, setFactIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      searchPlaces(query || "*", emptyConstraints)
        .then((result) => {
          if (!active) return;
          setOptions(result.items);
          setPlaceId((current) => current || params.get("place") || "");
          setLoadError("");
        })
        .catch((reason: unknown) => {
          if (active)
            setLoadError(
              reason instanceof Error
                ? reason.message
                : "Nie udało się pobrać miejsc.",
            );
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query, params]);

  useEffect(() => {
    let active = true;
    setPlace(null);
    setFactIds([]);
    if (placeId)
      getPlace(placeId)
        .then((result) => {
          if (!active) return;
          setPlace(result);
          setLoadError("");
        })
        .catch((reason: unknown) => {
          if (active)
            setLoadError(
              reason instanceof Error
                ? reason.message
                : "Nie udało się pobrać miejsca.",
            );
        });
    return () => {
      active = false;
    };
  }, [placeId]);

  const available = place?.facts.filter(needsVerification) || [];
  const selectedFacts = available.filter((item) => factIds.includes(item.id));
  const placeOptions =
    place && !options.some((item) => item.id === place.id)
      ? [place, ...options]
      : options;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!place || !selectedFacts.length || busy) return;
    setBusy(true);
    setError("");
    try {
      const missions = await requestVerificationMission(place.id, factIds);
      const missionParams = missions
        .map((mission) => `mission=${encodeURIComponent(mission.id)}`)
        .join("&");
      navigate(`/report/success?${missionParams}`, { state: { missions } });
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Nie udało się utworzyć misji.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (!session)
    return (
      <div className="page narrow">
        <PageHeading
          title="Poproś o weryfikację"
          description="Zaloguj się, aby utworzyć misję sprawdzenia informacji."
        />
        <Link
          className="button primary"
          to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
        >
          Zaloguj się
        </Link>
      </div>
    );

  return (
    <div className="page narrow">
      <Link to="/report" className="back-link">
        <ChevronLeft size={18} />
        Wróć do zgłoszeń
      </Link>
      <PageHeading
        title="Poproś o weryfikację"
        description="Wybierz miejsce i informację o niskiej pewności. Wysłanie prośby utworzy misję dla społeczności."
      />
      <form className="panel form-panel" onSubmit={submit}>
        <fieldset disabled={busy} className="form-fields">
          <label className="field">
            Szukaj miejsca
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Wpisz nazwę miejsca"
            />
          </label>
          <label className="field">
            Miejsce
            <select
              value={placeId}
              onChange={(event) => setPlaceId(event.target.value)}
              required
            >
              <option value="" disabled>
                Wybierz miejsce
              </option>
              {placeOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          {loadError && (
            <p className="warning-box" role="alert">
              {loadError}
            </p>
          )}
          {place && available.length === 0 && (
            <p className="empty-state">
              To miejsce nie ma informacji oznaczonych jako niepotwierdzone ani
              z pewnością do 60%.
            </p>
          )}
          {available.length > 0 && (
            <fieldset>
              <legend>
                Problemy lub parametry do sprawdzenia (możesz wybrać kilka)
              </legend>
              {available.map((item) => (
                <label className="check-field" key={item.id}>
                  <input
                    type="checkbox"
                    checked={factIds.includes(item.id)}
                    onChange={(event) =>
                      setFactIds((current) =>
                        event.target.checked
                          ? [...current, item.id]
                          : current.filter((id) => id !== item.id),
                      )
                    }
                  />
                  {labels[item.attribute] || item.attribute}
                  {item.confidence_percent !== null
                    ? ` · pewność ${item.confidence_percent}%`
                    : " · niepotwierdzona"}
                </label>
              ))}
            </fieldset>
          )}
          {selectedFacts.map((item) => (
            <FactRow key={item.id} fact={item} />
          ))}
          {error && (
            <p className="warning-box" role="alert">
              {error}
            </p>
          )}
          <button
            className="button primary full"
            disabled={busy || !selectedFacts.length}
          >
            {busy ? "Tworzenie misji…" : "Utwórz misję weryfikacji"}
            <ArrowRight size={18} />
          </button>
        </fieldset>
      </form>
    </div>
  );
}

export function ReportForm({ confirm = false }: { confirm?: boolean }) {
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { session, addReport } = useDemo();
  const [placeId, setPlaceId] = useState(params.get("place") || "");
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<PlaceSummary[]>([]);
  const [place, setPlace] = useState<Place | null>(null);
  const [attribute, setAttribute] = useState("accessible_toilet");
  const [answer, setAnswer] = useState("");
  const [description, setDescription] = useState("");
  const [metricValue, setMetricValue] = useState<Fact["value"]>(null);
  useEffect(() => setMetricValue(null), [placeId, attribute]);
  const [photo, setPhoto] = useState<File | null>(null);
  const today = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 10);
  const [date, setDate] = useState(today);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      searchPlaces(query, emptyConstraints)
        .then((result) => {
          if (!active) return;
          setOptions(result.items);
          setPlaceId((current) => current || result.items[0]?.id || "");
          setLoadError("");
        })
        .catch((reason: unknown) => {
          if (active)
            setLoadError(
              reason instanceof Error
                ? reason.message
                : "Nie udało się pobrać miejsc.",
            );
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query]);
  useEffect(() => {
    let active = true;
    setPlace(null);
    setAnswer("");
    if (placeId)
      getPlace(placeId)
        .then((result) => {
          if (!active) return;
          setPlace(result);
          setAttribute((current) =>
            result.facts.some((fact) => fact.attribute === current)
              ? current
              : result.facts[0]?.attribute || "",
          );
          setLoadError("");
        })
        .catch((reason: unknown) => {
          if (active)
            setLoadError(
              reason instanceof Error
                ? reason.message
                : "Nie udało się pobrać miejsca.",
            );
        });
    return () => {
      active = false;
    };
  }, [placeId]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!place || busy) return;
    const fact = place.facts.find((item) => item.attribute === attribute);
    if (!fact) {
      setError("Wybierz informację, której dotyczy zgłoszenie.");
      document.getElementById("report-attribute")?.focus();
      return;
    }
    if (photo && !description.trim()) {
      setError("Opisz, co przedstawia dołączone zdjęcie.");
      document.getElementById("report-description")?.focus();
      return;
    }
    if (confirm && !answer && metricValue === null) {
      setError("Wybierz odpowiedź.");
      document.querySelector<HTMLInputElement>('input[name="answer"]')?.focus();
      return;
    }
    if (!confirm && !description.trim() && !photo && metricValue === null) {
      setError("Dodaj opis lub zdjęcie.");
      document.getElementById("report-description")?.focus();
      return;
    }
    setError("");
    setBusy(true);
    try {
      const report = await withPhoto(photo, (photo_ids) =>
        createReport({
          target: { type: "place", id: place.id },
          kind:
            confirm && answer === "unknown"
              ? "missing_data"
              : confirm && answer === "yes"
                ? "confirmation"
                : "correction",
          fact_id: confirm && answer === "unknown" ? null : fact.id,
          description:
            description.trim() ||
            (confirm
              ? `${labels[fact.attribute] || fact.attribute}: ${answer === "yes" ? "potwierdzam" : answer === "no" ? "nie potwierdzam" : "nie wiem"}`
              : "Zdjęcie zaobserwowanego problemu"),
          observations:
            metricValue !== null
              ? [{ attribute: fact.attribute, value: metricValue }]
              : confirm && answer === "yes" && fact.value !== null
                ? [{ attribute: fact.attribute, value: fact.value }]
                : [],
          observed_at: new Date(`${date}T00:00:00`).toISOString(),
          photo_ids,
        }),
      );
      addReport(report);
      navigate(`/report/success?id=${encodeURIComponent(report.id)}`, {
        state: { report },
      });
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Nie udało się wysłać zgłoszenia. Dane formularza pozostały bez zmian.",
      );
    } finally {
      setBusy(false);
    }
  }
  if (!session)
    return (
      <div className="page narrow">
        <PageHeading
          title={confirm ? "Potwierdź informację" : "Zgłoś problem"}
          description="Zaloguj się, aby wysłać zgłoszenie i śledzić jego weryfikację."
        />
        <Link
          className="button primary"
          to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
        >
          Zaloguj się
        </Link>
      </div>
    );
  const available =
    place && !options.some((item) => item.id === place.id)
      ? [place, ...options]
      : options;
  const fact = place?.facts.find((item) => item.attribute === attribute);
  return (
    <div className="page narrow">
      <Link to="/report" className="back-link">
        <ChevronLeft size={18} />
        Wszystkie działania
      </Link>
      <PageHeading
        title={confirm ? "Potwierdź informację" : "Zgłoś problem"}
        description="Twoje zgłoszenie nie zmienia danych przed weryfikacją."
      />
      <form className="panel form-panel" onSubmit={submit}>
        <fieldset disabled={busy} className="form-fields">
          <label className="field">
            Szukaj miejsca do zgłoszenia
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Wpisz nazwę miejsca"
            />
          </label>
          <label className="field">
            Miejsce
            <select
              value={placeId}
              onChange={(event) => setPlaceId(event.target.value)}
              required
            >
              <option value="" disabled>
                Wybierz miejsce
              </option>
              {available.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          {loadError && (
            <p className="warning-box" role="alert">
              {loadError}
            </p>
          )}
          <label className="field">
            Informacja, której dotyczy zgłoszenie
            <select
              id="report-attribute"
              aria-invalid={
                error === "Wybierz informację, której dotyczy zgłoszenie." ||
                undefined
              }
              aria-describedby={
                error === "Wybierz informację, której dotyczy zgłoszenie."
                  ? "report-error"
                  : undefined
              }
              value={attribute}
              disabled={!place}
              onChange={(event) => {
                setAttribute(event.target.value);
                setMetricValue(null);
                setAnswer("");
              }}
            >
              {place?.facts.map((item) => (
                <option key={item.id} value={item.attribute}>
                  {labels[item.attribute] || item.attribute}
                </option>
              ))}
            </select>
          </label>
          {fact && <FactRow fact={fact} />}
          {fact && (
            <MetricInput
              attribute={fact.attribute}
              value={metricValue}
              onChange={setMetricValue}
            />
          )}
          {confirm && (
            <fieldset>
              <legend>Czy podana informacja nadal jest aktualna?</legend>
              {[
                { id: "yes", label: "Tak" },
                { id: "no", label: "Nie" },
                { id: "unknown", label: "Nie wiem" },
              ].map((item) => (
                <label className="check-field" key={item.id}>
                  <input
                    type="radio"
                    name="answer"
                    aria-invalid={error === "Wybierz odpowiedź." || undefined}
                    aria-describedby={
                      error === "Wybierz odpowiedź."
                        ? "report-error"
                        : undefined
                    }
                    value={item.id}
                    checked={answer === item.id}
                    onChange={() => setAnswer(item.id)}
                  />
                  {item.label}
                </label>
              ))}
            </fieldset>
          )}
          <label className="field">
            <span id="report-description-label">
              {confirm ? "Dodatkowy komentarz (opcjonalnie)" : "Opisz problem"}
            </span>
            <textarea
              id="report-description"
              aria-labelledby="report-description-label"
              aria-invalid={
                [
                  "Dodaj opis lub zdjęcie.",
                  "Opisz, co przedstawia dołączone zdjęcie.",
                ].includes(error) || undefined
              }
              aria-describedby={
                [
                  "Dodaj opis lub zdjęcie.",
                  "Opisz, co przedstawia dołączone zdjęcie.",
                ].includes(error)
                  ? "report-description-help report-error"
                  : "report-description-help"
              }
              required={Boolean(photo)}
              rows={4}
              maxLength={4000}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Np. podjazd jest obecnie zamknięty z powodu remontu."
            />
            <small id="report-description-help">
              {photo
                ? "Opis jest wymagany: wyjaśnij, co przedstawia zdjęcie."
                : confirm
                  ? "Komentarz jest opcjonalny."
                  : "Dodaj opis, zdjęcie z opisem lub wartość metryki."}
            </small>
          </label>
          <label className="field upload-field">
            Zdjęcie (opcjonalnie)
            <input
              type="file"
              aria-label="Zdjęcie (opcjonalnie)"
              aria-describedby="photo-help"
              accept="image/jpeg,image/png,image/webp"
              onChange={(event) => setPhoto(event.target.files?.[0] || null)}
            />
            <small id="photo-help">
              JPEG, PNG lub WebP, do 10 MiB. Zdjęcie będzie dostępne Tobie i
              moderatorowi.
            </small>
          </label>
          <label className="field">
            Data obserwacji
            <input
              type="date"
              value={date}
              required
              max={today}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          {error && (
            <p id="report-error" className="warning-box" role="alert">
              {error}
            </p>
          )}
          <button
            className="button primary full"
            disabled={busy || !place || !fact}
          >
            {busy ? "Wysyłanie…" : "Wyślij zgłoszenie"}
            <ArrowRight size={18} />
          </button>
        </fieldset>
      </form>
    </div>
  );
}

export function ReportSuccess() {
  const [params] = useSearchParams();
  const location = useLocation();
  const [report, setReport] = useState<Report | null>(
    location.state?.report || null,
  );
  const [missions, setMissions] = useState<Mission[]>(
    location.state?.missions ||
      (location.state?.mission ? [location.state.mission] : []),
  );
  const [error, setError] = useState("");
  const id = params.get("id");
  const missionIds = params.getAll("mission");
  const missionId = missionIds[0];
  useEffect(() => {
    let active = true;
    if (missionIds.length)
      Promise.all(missionIds.map((missionId) => getMission(missionId)))
        .then((items) => {
          if (active)
            setMissions((current) => (current.length ? current : items));
        })
        .catch((reason: unknown) => {
          if (active)
            setError(
              reason instanceof Error
                ? reason.message
                : "Nie udało się pobrać utworzonych misji.",
            );
        });
    if (id)
      getReport(id)
        .then((item) => {
          if (active) setReport(item);
        })
        .catch((reason: unknown) => {
          if (active)
            setError(
              reason instanceof Error
                ? reason.message
                : "Nie udało się pobrać zgłoszenia.",
            );
        });
    return () => {
      active = false;
    };
  }, [id, missionIds.join(",")]);
  if (missions.length)
    return (
      <div className="page narrow">
        <div className="panel success-state">
          <span className="success-icon">
            <Check size={36} />
          </span>
          <h1>Misja weryfikacji została utworzona</h1>
          <p>Inni użytkownicy mogą teraz sprawdzić wskazane informacje.</p>
          <div className="actions">
            {missions.map((mission) => (
              <Link
                className="button primary"
                key={mission.id}
                to={`/missions/${encodeURIComponent(mission.id)}`}
              >
                Zobacz misję: {mission.place_name}
              </Link>
            ))}
            <Link className="button subtle" to="/missions">
              Wszystkie misje
            </Link>
          </div>
        </div>
      </div>
    );
  if (!report)
    return (
      <div className="page narrow">
        <PageHeading
          title={
            error || (!id && !missionId)
              ? "Brak wysłanego zgłoszenia"
              : "Pobieranie zgłoszenia…"
          }
          description={error}
        />
        <Link className="button primary" to="/report">
          Zgłoś problem
        </Link>
      </div>
    );
  return (
    <div className="page narrow">
      <div className="panel success-state">
        <span className="success-icon">
          <Check size={36} />
        </span>
        <h1>Dziękujemy za pomoc!</h1>
        <p>Zgłoszenie wysłano i zapisano na Twoim koncie.</p>
        <p className="status warning">{reportStatus[report.status]}</p>
        <div className="actions">
          <Link className="button primary" to="/profile">
            Moje zgłoszenia
          </Link>
          <Link className="button subtle" to="/search">
            Znajdź miejsce
          </Link>
        </div>
      </div>
    </div>
  );
}
