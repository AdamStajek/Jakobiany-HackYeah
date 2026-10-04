import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ChevronLeft,
  MapPin,
  ShieldCheck,
  Bookmark,
  Flag,
  Route as RouteIcon,
  ArrowRight,
} from "lucide-react";
import { useDemo } from "../state/DemoContext";
import { FactRow } from "../components/Common";
import GooglePlaceCard from "../components/GooglePlaceCard";
import { getPlace } from "../data/api";
import type { Place, PlacePhoto } from "../data/types";
import { NotFound } from "./Info";
function PhotoFigure({ photo, name }: { photo: PlacePhoto; name: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <figure className="place-photo">
      {failed ? (
        <p>Zdjęcie jest chwilowo niedostępne.</p>
      ) : (
        <a href={photo.source_url} target="_blank" rel="noreferrer">
          <img
            src={photo.url}
            alt={`${name} — ${photo.description?.trim() || photo.title}`}
            loading="lazy"
            onError={() => setFailed(true)}
          />
        </a>
      )}
      <figcaption>
        {photo.author} ·{" "}
        {photo.license_url ? (
          <a href={photo.license_url} target="_blank" rel="noreferrer">
            {photo.license}
          </a>
        ) : (
          photo.license
        )}
        {" · "}
        <a href={photo.source_url} target="_blank" rel="noreferrer">
          Wikimedia Commons
        </a>
        {photo.credit && <span> · {photo.credit}</span>}
      </figcaption>
    </figure>
  );
}

export function PlacePage() {
  const { id } = useParams();
  const [p, setPlace] = useState<Place | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!id) return;
    getPlace(id)
      .then(setPlace)
      .catch((reason: unknown) =>
        setError(
          reason instanceof Error
            ? reason.message
            : "Nie udało się pobrać miejsca.",
        ),
      );
  }, [id]);
  const { saved, toggleSave, location } = useDemo();
  const distanceFromUser =
    p && location
      ? (() => {
          const earthRadiusM = 6_371_000;
          const lat1 = (location.lat * Math.PI) / 180;
          const lat2 = (p.location.lat * Math.PI) / 180;
          const deltaLat = lat2 - lat1;
          const deltaLon = ((p.location.lon - location.lon) * Math.PI) / 180;
          const a =
            Math.sin(deltaLat / 2) ** 2 +
            Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) ** 2;
          return earthRadiusM * 2 * Math.asin(Math.sqrt(Math.min(1, a)));
        })()
      : null;
  const [tab, setTab] = useState("Dostępność");
  const tabs = ["Dostępność", "Informacje", "Zdjęcia", "Źródła danych"];
  if (error)
    return (
      <div className="page narrow">
        <NotFound />
      </div>
    );
  if (!p)
    return (
      <div className="page narrow" role="status">
        Pobieranie danych miejsca…
      </div>
    );
  return (
    <div className="page place-page">
      <Link className="back-link" to="/search">
        <ChevronLeft size={18} />
        Wróć do wyników
      </Link>
      <div className="place-detail-grid">
        <aside>
          {p.photos?.[0] ? (
            <PhotoFigure
              key={p.photos[0].url}
              photo={p.photos[0]}
              name={p.name}
            />
          ) : (
            <div className="detail-image place-placeholder" aria-hidden="true">
              <MapPin size={42} />
            </div>
          )}
          <div className="place-address">
            <MapPin />
            <span>
              {p.address && p.address_is_nearest
                ? `Najbliższy adres: ${p.address}`
                : p.address || "Adres nieznany"}
              {distanceFromUser !== null && (
                <small>
                  {(distanceFromUser / 1000).toLocaleString("pl-PL", {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1,
                  })}{" "}
                  km od Ciebie
                </small>
              )}
            </span>
          </div>
          <GooglePlaceCard key={p.id} place={p} />
        </aside>
        <section>
          <div className="detail-heading">
            <div>
              <p className="eyebrow">{p.category}</p>
              <h1 data-no-translate>{p.name}</h1>
            </div>
            <button
              className="button subtle"
              onClick={() => toggleSave(p.id)}
              aria-pressed={saved.includes(p.id)}
            >
              <Bookmark size={19} />
              {saved.includes(p.id) ? "Zapisano" : "Zapisz"}
            </button>
          </div>
          <div className="detail-actions">
            <Link className="button primary" to={`/route?to=${p.id}`}>
              <RouteIcon size={20} />
              Wyznacz trasę
            </Link>
            <Link
              className="button subtle"
              to={`/report/problem?place=${p.id}`}
            >
              <Flag size={18} />
              Zgłoś problem
            </Link>
            <Link className="button subtle" to="/profile">
              <Bookmark size={18} />
              Zapisane miejsca
            </Link>
          </div>
          <div
            className="tabs"
            role="tablist"
            aria-label="Informacje o miejscu"
          >
            {tabs.map((t, index) => (
              <button
                key={t}
                role="tab"
                id={`place-tab-${index}`}
                aria-controls="place-tab"
                aria-selected={tab === t}
                tabIndex={tab === t ? 0 : -1}
                className={tab === t ? "active" : ""}
                onClick={() => setTab(t)}
                onKeyDown={(event) => {
                  const next =
                    event.key === "ArrowRight"
                      ? (index + 1) % tabs.length
                      : event.key === "ArrowLeft"
                        ? (index + tabs.length - 1) % tabs.length
                        : event.key === "Home"
                          ? 0
                          : event.key === "End"
                            ? tabs.length - 1
                            : null;
                  if (next === null) return;
                  event.preventDefault();
                  setTab(tabs[next]);
                  document.getElementById(`place-tab-${next}`)?.focus();
                }}
              >
                {t}
              </button>
            ))}
          </div>
          <div
            role="tabpanel"
            id="place-tab"
            tabIndex={0}
            aria-labelledby={`place-tab-${tabs.indexOf(tab)}`}
          >
            {tab === "Dostępność" ? (
              <>
                <h2 className="small-heading">
                  Konkretne informacje o dostępności
                </h2>
                <div className="facts-grid">
                  {(p.facts || []).map((f) => (
                    <FactRow key={f.id} fact={f} />
                  ))}
                </div>
                <Link
                  className="button subtle"
                  to={`/report/confirm?place=${p.id}`}
                >
                  Potwierdź informację <ArrowRight size={18} />
                </Link>
              </>
            ) : tab === "Informacje" ? (
              <div className="info-panel">
                <h2>O miejscu</h2>
                {p.website_description && <p>{p.website_description}</p>}
                {p.accessibility_summary && <p>{p.accessibility_summary}</p>}
                <p>
                  <strong>
                    {p.address_is_nearest ? "Najbliższy adres:" : "Adres:"}
                  </strong>{" "}
                  {p.address || "Adres nieznany"}
                </p>
                {p.operator && (
                  <p>
                    <strong>Operator:</strong> {p.operator}
                  </p>
                )}
                {p.phone && (
                  <p>
                    <strong>Telefon:</strong>{" "}
                    <a href={`tel:${p.phone}`}>{p.phone}</a>
                  </p>
                )}
                {(p.opening_hours || p.website_opening_hours) && (
                  <p>
                    <strong>Godziny otwarcia:</strong>{" "}
                    {p.opening_hours || p.website_opening_hours}
                  </p>
                )}
                {p.access && (
                  <p>
                    <strong>Dostęp:</strong> {p.access}
                  </p>
                )}
                {p.website && (
                  <p>
                    <a href={p.website} target="_blank" rel="noreferrer">
                      Strona miejsca
                    </a>
                  </p>
                )}
              </div>
            ) : tab === "Zdjęcia" ? (
              <div className="info-panel">
                {p.photos?.length ? (
                  p.photos.map((photo) => (
                    <PhotoFigure key={photo.url} photo={photo} name={p.name} />
                  ))
                ) : (
                  <p>Brak zdjęć tego miejsca w bazie.</p>
                )}
              </div>
            ) : (
              <div className="source-cards">
                {[
                  ...p.attribution,
                  ...(p.website_source ? [p.website_source] : []),
                ].map((s, i) => (
                  <div className="panel" key={`${s.type}-${i}`}>
                    <ShieldCheck />
                    <h3>{s.label}</h3>
                    <p>Źródło: {s.type === "osm" ? "OpenStreetMap" : s.type}</p>
                    <p>
                      Informacje źródłowe są niepotwierdzone; sprawdź daty
                      poszczególnych faktów.
                    </p>
                    {s.url && <a href={s.url}>Licencja {s.license}</a>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
