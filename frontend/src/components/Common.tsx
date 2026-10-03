import {
  Bookmark,
  Check,
  ChevronRight,
  MapPin,
  Search,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useState, type FormEvent } from "react";
import type { Assessment, Fact, Place } from "../data/types";
import { formatFact, labels } from "../data/mock";
export function SearchBox({
  initial = "",
  compact = false,
}: {
  initial?: string;
  compact?: boolean;
}) {
  const [query, setQuery] = useState(initial);
  const navigate = useNavigate();
  function submit(e: FormEvent) {
    e.preventDefault();
    navigate(`/search?q=${encodeURIComponent(query.trim())}`);
  }
  return (
    <form
      className={`search-box ${compact ? "compact" : ""}`}
      onSubmit={submit}
    >
      <Search aria-hidden="true" size={23} />
      <label
        className="sr-only"
        htmlFor={compact ? "sidebar-search" : "main-search"}
      >
        Wyszukaj miejsce lub kategorię
      </label>
      <input
        id={compact ? "sidebar-search" : "main-search"}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Wyszukaj miejsce lub trasę"
      />
      <button className="button primary" type="submit">
        Szukaj
      </button>
    </form>
  );
}
export function Status({ assessment }: { assessment: Assessment }) {
  return (
    <span
      className={`status ${assessment.status === "meets_requirements" ? "good" : "warning"}`}
    >
      {assessment.status === "meets_requirements" ? (
        <Check size={16} />
      ) : (
        <TriangleAlert size={16} />
      )}{" "}
      {assessment.summary}
    </span>
  );
}
export function PlaceCard({
  place,
  assessment,
  saved,
  toggle,
}: {
  place: Place;
  assessment: Assessment;
  saved: boolean;
  toggle: () => void;
}) {
  return (
    <article className="place-card">
      <Link to={`/place/${place.id}`} className="place-image">
        <img src={`/illustrations/${place.demo.image}.svg`} alt="" />
      </Link>
      <div className="place-card-body">
        <p className="eyebrow">{place.category}</p>
        <h3>
          <Link to={`/place/${place.id}`}>{place.name}</Link>
        </h3>
        <p className="muted location">
          <MapPin size={15} />
          {place.address} · {(place.distance_m / 1000).toLocaleString("pl-PL")}{" "}
          km
        </p>
        <Status assessment={assessment} />
        <div className="feature-chips">
          {place.facts
            .filter((f) =>
              ["steps_count", "entrance_width_cm"].includes(f.attribute),
            )
            .map((f) => (
              <span key={f.id}>
                <Check size={14} />
                {formatFact(f)}
              </span>
            ))}
        </div>
        <p className="reliability">
          <ShieldCheck size={16} /> Źródła i daty dostępne w szczegółach
        </p>
      </div>
      <button
        className={`icon-button bookmark ${saved ? "is-saved" : ""}`}
        aria-label={`${saved ? "Usuń z zapisanych" : "Zapisz"}: ${place.name}`}
        aria-pressed={saved}
        onClick={toggle}
      >
        <Bookmark size={21} fill={saved ? "currentColor" : "none"} />
      </button>
      <Link
        className="card-arrow"
        aria-label={`Szczegóły: ${place.name}`}
        to={`/place/${place.id}`}
      >
        <ChevronRight />
      </Link>
    </article>
  );
}
export function FactRow({ fact }: { fact: Fact }) {
  return (
    <div className="fact-row">
      <div
        className={`fact-symbol ${fact.status === "confirmed" ? "good" : "warning"}`}
      >
        {fact.status === "confirmed" ? (
          <Check size={18} />
        ) : (
          <TriangleAlert size={18} />
        )}
      </div>
      <div>
        <strong>{labels[fact.attribute]}</strong>
        <p>{formatFact(fact)}</p>
        <small>
          {fact.sources.map((s) => s.label).join(", ") || "Brak źródła"} ·{" "}
          {fact.observed_at
            ? new Date(fact.observed_at).toLocaleDateString("pl-PL", {
                timeZone: "Europe/Warsaw",
              })
            : "Brak daty obserwacji"}{" "}
          ·{" "}
          {fact.confidence_percent === null
            ? "Brak oceny wiarygodności"
            : `Wiarygodność: ${fact.confidence_percent}%`}
        </small>
        {fact.alternatives && (
          <ul>
            {fact.alternatives.map((a, i) => (
              <li key={i}>
                {a.value === true ? "Tak" : "Nie"} — {a.source.label},{" "}
                {new Date(a.observed_at).toLocaleDateString("pl-PL", {
                  timeZone: "Europe/Warsaw",
                })}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="page-heading">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1>{title}</h1>
      {description && <p className="muted">{description}</p>}
    </div>
  );
}
