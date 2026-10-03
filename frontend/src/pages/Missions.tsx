import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowRight,
  Star,
  Flag,
  MapPin,
  TriangleAlert,
  ChevronLeft,
} from "lucide-react";
import { useDemo } from "../state/DemoContext";
import { PageHeading } from "../components/Common";
import { places, missions } from "../data/mock";
import { NotFound } from "./Info";
export function MissionsPage() {
  const { progress } = useDemo();
  const [tab, setTab] = useState("available");
  const shown = missions.filter((m) => tab === "available" || progress[m.id]);
  return (
    <div className="page narrow">
      <PageHeading
        eyebrow="WSPÓLNIE ODKRYWAMY WIĘCEJ"
        title="Twoje misje"
        description="Pomagaj innym odkrywać Kraków bez barier."
      />
      <div className="mission-banner">
        <Star size={45} />
        <div>
          <h2>Małe zadania. Wielka różnica.</h2>
          <p>Sprawdź informacje w okolicy i pomóż uzupełnić mapę.</p>
        </div>
        <span>DEMO</span>
      </div>
      <div className="tabs">
        <button
          className={tab === "available" ? "active" : ""}
          onClick={() => setTab("available")}
        >
          Dostępne misje
        </button>
        <button
          className={tab === "progress" ? "active" : ""}
          onClick={() => setTab("progress")}
        >
          Moje postępy
        </button>
      </div>
      {shown.map((m) => (
        <Link
          className="panel mission-card"
          key={m.id}
          to={`/missions/${m.id}`}
        >
          <img
            src={`/illustrations/${places.find((p) => p.id === m.place)!.demo.image}.svg`}
            alt=""
          />
          <div>
            <h2>{m.title}</h2>
            <p className="muted">
              Około {m.time} minut · {progress[m.id] || "Dostępna"}
            </p>
            <strong className="points">+{m.points} pkt po zatwierdzeniu</strong>
          </div>
          <ArrowRight />
        </Link>
      ))}
      {!shown.length && (
        <div className="empty-state">
          <Flag />
          <h2>Tu pojawią się Twoje misje</h2>
          <p>Wybierz zadanie z zakładki „Dostępne misje”.</p>
        </div>
      )}
      <p className="muted">
        Misje i punkty są podglądem funkcji planowanej. W demonstracji nie
        naliczamy nagród.
      </p>
    </div>
  );
}
export function MissionPage() {
  const { id } = useParams();
  const m = missions.find((m) => m.id === id);
  const { progress, setProgress, notify } = useDemo();
  const [answer, setAnswer] = useState("");
  if (!m) return <NotFound />;
  return (
    <div className="page narrow">
      <Link className="back-link" to="/missions">
        <ChevronLeft size={18} />
        Wszystkie misje
      </Link>
      <PageHeading
        title={m.title}
        description={`Przykładowa misja · ${m.time} minut · ${m.points} punktów po zatwierdzeniu`}
      />
      <div className="panel">
        <p>
          Sprawdź wskazane miejsce i opisz zaobserwowane warunki. Nie zakładaj
          dostępności, jeśli nie możesz jej potwierdzić.
        </p>
        <Link className="button subtle" to={`/place/${m.place}`}>
          Zobacz miejsce <MapPin size={18} />
        </Link>
        {!progress[m.id] ? (
          <button
            className="button primary"
            onClick={() => setProgress(m.id, "W trakcie")}
          >
            Rozpocznij przykładową misję
          </button>
        ) : progress[m.id] === "W trakcie" ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setProgress(m.id, "Oczekuje na weryfikację");
              notify(
                "Przykładowa odpowiedź została zapisana. Punkty wymagają zatwierdzenia.",
              );
            }}
          >
            <label className="field">
              Co udało Ci się sprawdzić?
              <textarea
                required
                minLength={10}
                maxLength={4000}
                rows={4}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
              />
            </label>
            <button className="button primary">
              Zapisz odpowiedź do weryfikacji
            </button>
          </form>
        ) : (
          <p className="status warning">
            <TriangleAlert size={18} />
            Oczekuje na weryfikację · 0 naliczonych punktów
          </p>
        )}
      </div>
    </div>
  );
}
