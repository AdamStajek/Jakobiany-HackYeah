import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Bookmark, ArrowRight } from "lucide-react";
import { useDemo } from "../state/DemoContext";
import { PageHeading } from "../components/Common";
import { EvidencePhotos } from "../components/EvidencePhotos";
import { getPlace } from "../data/api";
import { reportStatus } from "./Reports";

export function Profile() {
  const {
    saved,
    profile,
    reports,
    user,
    session,
    signOut,
    activity,
    refreshActivity,
  } = useDemo();
  const [names, setNames] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    const ids = [
      ...new Set([
        ...saved,
        ...reports
          .filter((report) => report.target.type === "place")
          .map((report) => report.target.id),
      ]),
    ];
    Promise.allSettled(
      ids.map(async (id) => ({ id, name: (await getPlace(id)).name })),
    ).then((results) => {
      if (active)
        setNames(
          Object.fromEntries(
            results.flatMap((result) =>
              result.status === "fulfilled"
                ? [[result.value.id, result.value.name]]
                : [],
            ),
          ),
        );
    });
    return () => {
      active = false;
    };
  }, [saved, reports]);
  useEffect(() => {
    if (session)
      refreshActivity().catch((reason: unknown) =>
        setError(
          reason instanceof Error
            ? reason.message
            : "Nie udało się pobrać aktywności.",
        ),
      );
  }, [session?.user.id]);
  async function logOut() {
    setBusy(true);
    setError("");
    try {
      await signOut();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Nie udało się wylogować.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page">
      <PageHeading
        title={user ? `Cześć, ${user}!` : "Twój profil"}
        description={
          session
            ? "Twoje potrzeby i aktywność są zapisane na koncie."
            : "Zaloguj się, aby zapisywać profil, miejsca i postępy misji."
        }
      />
      {error && (
        <p className="warning-box" role="alert">
          {error}
        </p>
      )}
      <div className="profile-grid">
        <section className="panel">
          <h2>Moje potrzeby</h2>
          <p>
            {Object.values(profile?.constraints || {}).some(
              (value) => value !== null && value !== undefined,
            )
              ? "Twoje preferencje są zapisane. Możesz je sprawdzić i edytować."
              : "Nie określono jeszcze potrzeb."}
          </p>
          <Link className="button primary" to="/profile/setup">
            Edytuj profil potrzeb
          </Link>
          {session ? (
            <button className="button subtle" disabled={busy} onClick={logOut}>
              {busy ? "Wylogowywanie…" : "Wyloguj się"}
            </button>
          ) : (
            <Link className="button subtle" to="/login">
              Zaloguj się
            </Link>
          )}
          <hr />
          <h3>Twój krakowski tytuł</h3>
          <p className="status good">
            {activity.contributor_title || "Krakowski Odkrywca"}
          </p>
          <p className="muted">
            Tytuł zależy od wiarygodności i liczby ocenionych zgłoszeń. Każde
            rzetelne zgłoszenie pomaga odkrywać Kraków bez barier.
          </p>
          <hr />
          <h3>Twoje punkty</h3>
          <p className="points">{activity.points} pkt</p>
          <Link className="button subtle" to="/missions">
            Moje misje
          </Link>
          {session?.user.roles.includes("moderator") && (
            <>
              <hr />
              <Link className="button primary" to="/review">
                Weryfikuj zgłoszenia i misje
              </Link>
            </>
          )}
        </section>
        <section className="panel">
          <h2>
            Zapisane miejsca <span className="count">{saved.length}</span>
          </h2>
          {saved.length ? (
            saved.map((id) => (
              <Link
                key={id}
                className="saved-row"
                to={`/place/${encodeURIComponent(id)}`}
              >
                <Bookmark size={20} />
                {names[id] || id}
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
          {session && (
            <button
              className="text-button"
              onClick={() => {
                setError("");
                refreshActivity().catch((reason: unknown) =>
                  setError(
                    reason instanceof Error
                      ? reason.message
                      : "Nie udało się odświeżyć zgłoszeń.",
                  ),
                );
              }}
            >
              Odśwież statusy
            </button>
          )}
          {reports.length ? (
            reports.map((report) => (
              <div className="report-row" key={report.id}>
                <strong>{names[report.target.id] || report.target.id}</strong>
                <p>{report.description}</p>
                <span
                  className={`status ${report.status === "accepted" ? "good" : "warning"}`}
                >
                  {reportStatus[report.status]}
                </span>
                {report.review_comment && (
                  <p>Komentarz moderatora: {report.review_comment}</p>
                )}
                <EvidencePhotos
                  ids={report.photo_ids}
                  description={report.description}
                />
              </div>
            ))
          ) : (
            <p className="muted">Nie masz jeszcze zgłoszeń.</p>
          )}
        </section>
      </div>
    </div>
  );
}
