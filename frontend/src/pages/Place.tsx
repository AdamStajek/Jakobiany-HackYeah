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
import { Status, FactRow } from "../components/Common";
import { getPlace } from "../data/api";
import type { Place } from "../data/types";
import { NotFound } from "./Info";
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
  const { saved, toggleSave } = useDemo();
  const [tab, setTab] = useState("Dostępność");
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
          <div className="detail-image place-placeholder" aria-hidden="true">
            <MapPin size={42} />
          </div>
          <div className="place-address">
            <MapPin />
            <span>
              {p.address || "Adres nieznany"}
              {p.distance_m !== null && (
                <small>
                  {(p.distance_m / 1000).toLocaleString("pl-PL")} km od punktu
                  wyszukiwania
                </small>
              )}
            </span>
          </div>
          <div className="callout">
            <ShieldCheck />
            <p>
              Sprawdź konkretne cechy miejsca. Ocena dopasowania zależy od
              wybranych potrzeb.
            </p>
          </div>
        </aside>
        <section>
          <div className="detail-heading">
            <div>
              <p className="eyebrow">{p.category}</p>
              <h1>{p.name}</h1>
              <Status
                assessment={
                  p.assessment || {
                    status: "uncertain",
                    summary: "Dopasowanie nieznane.",
                    reasons: [],
                  }
                }
              />
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
            {["Dostępność", "Informacje", "Zdjęcia", "Źródła danych"].map(
              (t) => (
                <button
                  key={t}
                  role="tab"
                  id={`tab-${t}`}
                  aria-controls="place-tab"
                  aria-selected={tab === t}
                  className={tab === t ? "active" : ""}
                  onClick={() => setTab(t)}
                >
                  {t}
                </button>
              ),
            )}
          </div>
          <div role="tabpanel" id="place-tab" aria-labelledby={`tab-${tab}`}>
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
                  <strong>Adres:</strong> {p.address || "Adres nieznany"}
                </p>
                {p.operator && (
                  <p>
                    <strong>Operator:</strong> {p.operator}
                  </p>
                )}
                {p.phone && (
                  <p>
                    <strong>Telefon z OSM:</strong>{" "}
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
                <p>Brak zdjęć tego miejsca w bazie.</p>
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
