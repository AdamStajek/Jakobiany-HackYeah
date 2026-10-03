import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Bookmark, ArrowRight } from "lucide-react";
import { useDemo } from "../state/DemoContext";
import { PageHeading } from "../components/Common";
import { places } from "../data/mock";
export function Profile() {
  const { saved, constraints, reports, user, setUser } = useDemo();
  const [large, setLarge] = useState(
    document.documentElement.classList.contains("large-text"),
  );
  const [contrast, setContrast] = useState(
    document.documentElement.classList.contains("high-contrast"),
  );
  useEffect(() => {
    document.documentElement.classList.toggle("large-text", large);
  }, [large]);
  useEffect(() => {
    document.documentElement.classList.toggle("high-contrast", contrast);
  }, [contrast]);
  return (
    <div className="page">
      <PageHeading
        title={user ? `Cześć, ${user}!` : "Twój profil"}
        description="Ustawienia i aktywność w bieżącej sesji demonstracyjnej."
      />
      <div className="profile-grid">
        <section className="panel">
          <h2>Moje potrzeby</h2>
          <p>
            {Object.values(constraints).some((v) => v !== null)
              ? "Twoje preferencje są aktywne. Możesz je sprawdzić i edytować."
              : "Nie określono jeszcze potrzeb."}
          </p>
          <Link className="button primary" to="/profile/setup">
            Edytuj profil potrzeb
          </Link>
          <hr />
          <h3>Dostępność interfejsu</h3>
          <label className="check-field">
            <input
              type="checkbox"
              checked={large}
              onChange={(e) => setLarge(e.target.checked)}
            />
            Większy tekst
          </label>
          <label className="check-field">
            <input
              type="checkbox"
              checked={contrast}
              onChange={(e) => setContrast(e.target.checked)}
            />
            Zwiększony kontrast
          </label>
          {user ? (
            <button className="button subtle" onClick={() => setUser(null)}>
              Wyloguj z konta demo
            </button>
          ) : (
            <Link className="button subtle" to="/login">
              Wejdź na konto demo
            </Link>
          )}
        </section>
        <section className="panel">
          <h2>
            Zapisane miejsca <span className="count">{saved.length}</span>
          </h2>
          {saved.length ? (
            saved.map((id) => (
              <Link key={id} className="saved-row" to={`/place/${encodeURIComponent(id)}`}>
                <Bookmark size={20} />
                {places.find((p) => p.id === id)?.name}
                <ArrowRight size={18} />
              </Link>
            ))
          ) : (
            <p className="muted">
              Zapisuj miejsca przyciskiem z zakładką, aby łatwo do nich wrócić.
            </p>
          )}
          <hr />
          <h2>Moje zgłoszenia</h2>
          {reports.length ? (
            reports.map((r) => (
              <div className="report-row" key={r.id}>
                <strong>
                  {places.find((p) => p.id === r.target.id)?.name}
                </strong>
                <p>{r.description}</p>
                <span className="status warning">Oczekuje na weryfikację</span>
              </div>
            ))
          ) : (
            <p className="muted">Nie masz jeszcze przykładowych zgłoszeń.</p>
          )}
        </section>
      </div>
    </div>
  );
}
