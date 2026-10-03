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
} from "lucide-react";
import { useDemo } from "../state/DemoContext";
import { PageHeading, FactRow } from "../components/Common";
import { labels } from "../data/mock";
import {
  createReport,
  getPlace,
  getReport,
  searchPlaces,
  withPhoto,
} from "../data/api";
import {
  emptyConstraints,
  type Place,
  type PlaceSummary,
  type Report,
} from "../data/types";

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
        title="Zgłoś lub potwierdź informację"
        description="Pomóż innym znaleźć drogę. Każda informacja trafia do weryfikacji."
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
        <Link className="panel" to="/report/confirm">
          <span className="option-icon good">
            <Check />
          </span>
          <h2>Potwierdź informację</h2>
          <p>Sprawdź, czy dane o miejscu są nadal aktualne.</p>
          <span className="button subtle">
            Potwierdź <ArrowRight size={18} />
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
      return;
    }
    if (confirm && !answer) {
      setError("Wybierz odpowiedź.");
      return;
    }
    if (!confirm && !description.trim() && !photo) {
      setError("Dodaj opis lub zdjęcie.");
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
            confirm && answer === "yes" && fact.value !== null
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
              value={attribute}
              disabled={!place}
              onChange={(event) => {
                setAttribute(event.target.value);
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
            {confirm ? "Dodatkowy komentarz (opcjonalnie)" : "Opisz problem"}
            <textarea
              rows={4}
              maxLength={4000}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Np. podjazd jest obecnie zamknięty z powodu remontu."
            />
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
            <p className="warning-box" role="alert">
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
  const [error, setError] = useState("");
  const id = params.get("id");
  useEffect(() => {
    let active = true;
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
  }, [id]);
  if (!report)
    return (
      <div className="page narrow">
        <PageHeading
          title={
            error || !id
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
