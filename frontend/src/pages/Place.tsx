import { useState } from "react";
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
import { assess, places } from "../data/mock";
import { NotFound } from "./Info";
export function PlacePage() {
  const { id } = useParams();
  const p = places.find((p) => p.id === id);
  const { constraints, saved, toggleSave } = useDemo();
  const [tab, setTab] = useState("Dostępność");
  if (!p) return <NotFound />;
  return (
    <div className="page place-page">
      <Link className="back-link" to="/search">
        <ChevronLeft size={18} />
        Wróć do wyników
      </Link>
      <div className="place-detail-grid">
        <aside>
          <img
            className="detail-image"
            src={`/illustrations/${p.demo.image}.svg`}
            alt={`Ilustracja miejsca: ${p.name}`}
          />
          <div className="photo-note">
            Ilustracja demonstracyjna, nie zdjęcie obiektu
          </div>
          <div className="place-address">
            <MapPin />
            <span>
              {p.address}
              <small>
                {(p.distance_m / 1000).toLocaleString("pl-PL")} km od punktu
                demonstracyjnego
              </small>
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
              <Status assessment={assess(p, constraints)} />
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
                  {p.facts.map((f) => (
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
                <p>{p.demo.description}</p>
                <p>
                  <strong>Adres:</strong> {p.address}
                </p>
                <p>
                  Brak potwierdzonych informacji o godzinach otwarcia, telefonie
                  i stronie internetowej.
                </p>
              </div>
            ) : tab === "Zdjęcia" ? (
              <div className="info-panel">
                <img
                  className="gallery-image"
                  src={`/illustrations/${p.demo.image}.svg`}
                  alt="Ilustracja demonstracyjna obiektu"
                />
                <p>
                  Galeria demonstracyjna. Zdjęcia wejścia i udogodnień zostaną
                  dodane po integracji.
                </p>
              </div>
            ) : (
              <div className="source-cards">
                {p.attribution.map((s) => (
                  <div className="panel" key={s.type}>
                    <ShieldCheck />
                    <h3>{s.label}</h3>
                    <p>Aktualizacja: 02.10.2026</p>
                    <p>
                      Dane przykładowe. Wiarygodność jest podana osobno przy
                      każdym fakcie.
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
