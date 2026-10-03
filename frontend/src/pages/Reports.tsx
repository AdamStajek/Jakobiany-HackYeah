import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  TriangleAlert,
  Check,
  ShieldCheck,
  ChevronLeft,
} from "lucide-react";
import { useDemo } from "../state/DemoContext";
import { PageHeading, FactRow } from "../components/Common";
import { places, labels } from "../data/mock";
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
          W tej wersji zgłoszenia zapisujemy tylko w pamięci aplikacji. Nie są
          wysyłane do moderatora.
        </p>
      </div>
    </div>
  );
}
export function ReportForm({ confirm = false }: { confirm?: boolean }) {
  const [params] = useSearchParams();
  const [placeId, setPlaceId] = useState(params.get("place") || places[0].id);
  const [attribute, setAttribute] = useState("accessible_toilet");
  const [answer, setAnswer] = useState("");
  const [description, setDescription] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [date, setDate] = useState("2026-10-03");
  const [error, setError] = useState("");
  const { addReport } = useDemo();
  const navigate = useNavigate();
  const p = places.find((p) => p.id === placeId)!;
  function submit(e: FormEvent) {
    e.preventDefault();
    if (confirm && !answer) {
      setError("Wybierz odpowiedź.");
      return;
    }
    if (!confirm && !description.trim() && !photo) {
      setError("Dodaj opis lub zdjęcie.");
      return;
    }
    if (
      photo &&
      (!["image/jpeg", "image/png", "image/webp"].includes(photo.type) ||
        photo.size > 10 * 1024 * 1024)
    ) {
      setError("Dodaj zdjęcie JPEG, PNG lub WebP o rozmiarze do 10 MiB.");
      return;
    }
    const fact = p.facts.find((f) => f.attribute === attribute)!;
    addReport({
      id: `demo_${Date.now()}`,
      target: { type: "place", id: placeId },
      kind: confirm
        ? answer === "unknown"
          ? "missing_data"
          : answer === "yes"
            ? "confirmation"
            : "correction"
        : "correction",
      fact_id: confirm && answer === "unknown" ? null : fact.id,
      description:
        description.trim() ||
        (confirm
          ? `${labels[fact.attribute]}: ${answer === "yes" ? "potwierdzam" : answer === "no" ? "nie potwierdzam" : "nie wiem"}`
          : "Dodano zdjęcie demonstracyjne"),
      observations: [],
      status: "pending",
      observed_at: `${date}T12:00:00Z`,
      demo_photo_name: photo?.name || null,
    });
    navigate("/report/success");
  }
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
        <label className="field">
          Miejsce
          <select
            value={placeId}
            onChange={(e) => {
              setPlaceId(e.target.value);
              setAnswer("");
            }}
          >
            {places.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Informacja, której dotyczy zgłoszenie
          <select
            value={attribute}
            onChange={(e) => {
              setAttribute(e.target.value);
              setAnswer("");
            }}
          >
            {p.facts.map((f) => (
              <option key={f.id} value={f.attribute}>
                {labels[f.attribute]}
              </option>
            ))}
          </select>
        </label>
        <FactRow fact={p.facts.find((f) => f.attribute === attribute)!} />
        {confirm && (
          <fieldset>
            <legend>Czy podana informacja nadal jest aktualna?</legend>
            {[
              { id: "yes", label: "Tak" },
              { id: "no", label: "Nie" },
              { id: "unknown", label: "Nie wiem" },
            ].map((a) => (
              <label className="check-field" key={a.id}>
                <input
                  type="radio"
                  name="answer"
                  value={a.id}
                  checked={answer === a.id}
                  onChange={() => setAnswer(a.id)}
                />
                {a.label}
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
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Np. podjazd jest obecnie zamknięty z powodu remontu."
          />
        </label>
        <label className="field upload-field">
          Zdjęcie (opcjonalnie)
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => setPhoto(e.target.files?.[0] || null)}
          />
          <small>
            JPEG, PNG lub WebP, do 10 MiB. Plik nie opuszcza przeglądarki.
          </small>
        </label>
        <label className="field">
          Data obserwacji
          <input
            type="date"
            value={date}
            required
            max="2026-10-03"
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
        {error && (
          <p className="warning-box" role="alert">
            {error}
          </p>
        )}
        <button className="button primary full">
          Zapisz przykładowe zgłoszenie <ArrowRight size={18} />
        </button>
      </form>
    </div>
  );
}
export function ReportSuccess() {
  return (
    <div className="page narrow">
      <div className="panel success-state">
        <span className="success-icon">
          <Check size={36} />
        </span>
        <h1>Dziękujemy za pomoc!</h1>
        <p>
          Przykładowe zgłoszenie zapisano w tej sesji. Status: oczekuje na
          weryfikację.
        </p>
        <p className="muted">
          To demonstracja. Zgłoszenie nie zostało wysłane do serwera.
        </p>
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
