import {
  Check,
  MapPin,
  Route as RouteIcon,
  Search,
  TriangleAlert,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useId, useState, type FormEvent } from "react";
import type { Assessment, Fact, PlaceSummary } from "../data/types";
import { formatFact, labels } from "../data/mock";
import { useDemo } from "../state/DemoContext";
export function SearchBox({
  initial = "",
  compact = false,
}: {
  initial?: string;
  compact?: boolean;
}) {
  const [query, setQuery] = useState(initial);
  const inputId = useId();
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
      <label className="sr-only" htmlFor={inputId}>
        Wyszukaj miejsce
      </label>
      <input
        id={inputId}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Wyszukaj miejsce"
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
  onShowOnMap,
}: {
  place: PlaceSummary;
  onShowOnMap?: () => void;
}) {
  const navigate = useNavigate();
  const { location } = useDemo();
  const image = place.photos?.[0] ? (
    <img
      src={place.photos[0].url}
      alt={`${place.name} — ${place.photos[0].description?.trim() || place.photos[0].title}`}
      loading="lazy"
    />
  ) : (
    <MapPin size={34} aria-hidden="true" />
  );
  return (
    <article className="place-card">
      {place.is_example ? (
        <div className="place-image" aria-hidden="true">
          {image}
        </div>
      ) : (
        <Link
          to={`/place/${encodeURIComponent(place.id)}`}
          className="place-image"
          aria-label={place.name}
          data-no-translate
        >
          {image}
        </Link>
      )}
      <div className="place-card-body">
        {place.is_example && (
          <p className="example-badge">
            Przykład — dane poglądowe, niezweryfikowane
          </p>
        )}
        <p className="eyebrow">{place.category}</p>
        <h3>
          {place.is_example ? (
            <span>{place.name}</span>
          ) : (
            <Link
              to={`/place/${encodeURIComponent(place.id)}`}
              data-no-translate
            >
              {place.name}
            </Link>
          )}
        </h3>
        <p className="muted location">
          <MapPin size={15} />
          {place.address && place.address_is_nearest
            ? `Najbliższy adres: ${place.address}`
            : place.address || "Adres nieznany"}
          {place.distance_m !== null &&
            ` · ${(place.distance_m / 1000).toLocaleString("pl-PL", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} km od Ciebie`}
        </p>
        {place.assessment && <Status assessment={place.assessment} />}
        <div className="place-card-actions">
          {onShowOnMap && (
            <button className="button subtle" onClick={onShowOnMap}>
              Pokaż na mapie
            </button>
          )}
          {!place.is_example && (
            <button
              className="button subtle place-route-button"
              onClick={() =>
                navigate(
                  `/route?to=${encodeURIComponent(place.id)}&from=${location ? "location" : "empty"}`,
                )
              }
            >
              <RouteIcon size={17} />
              Wyznacz trasę
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
export function FactRow({ fact }: { fact: Fact }) {
  const osmModifiedAt = fact.sources.find((source) => source.modified_at)
    ?.modified_at;
  const confidenceLabels = {
    certain: "Pewne",
    probable: "Prawdopodobne",
    uncertain: "Niepewne",
  };
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
        <strong>{labels[fact.attribute] || fact.attribute}</strong>
        <p>{formatFact(fact)}</p>
        <small>
          {fact.sources.map((s) => s.label).join(", ") || "Brak źródła"} ·{" "}
          {fact.observed_at
            ? new Date(fact.observed_at).toLocaleDateString("pl-PL", {
                timeZone: "Europe/Warsaw",
              })
            : "Brak daty obserwacji"}{" "}
          {osmModifiedAt && (
            <>
              · Ostatnia edycja w OSM: {new Date(osmModifiedAt).toLocaleDateString(
                "pl-PL",
                { timeZone: "Europe/Warsaw" },
              )}{" "}
            </>
          )}
          · Wiarygodność: {confidenceLabels[fact.confidence_level]} (
          {fact.confidence_score.toLocaleString("pl-PL", {
            maximumFractionDigits: 2,
          })}{" "}
          pkt)
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
      <h1 tabIndex={-1}>{title}</h1>
      {description && <p className="muted">{description}</p>}
    </div>
  );
}
