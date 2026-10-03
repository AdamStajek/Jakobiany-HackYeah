import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { PageHeading } from "../components/Common";
import { EvidencePhotos } from "../components/EvidencePhotos";
import { useDemo } from "../state/DemoContext";
import {
  getMissions,
  listAll,
  reviewMission,
  reviewReport,
  type Mission,
  type MissionProgress,
} from "../data/api";
import type { Report } from "../data/types";

function ReviewCard({
  report,
  progress,
  mission,
  done,
}: {
  report: Report;
  progress?: MissionProgress;
  mission?: Mission;
  done: (id: string) => void;
}) {
  const { notify } = useDemo();
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const button = (event.nativeEvent as SubmitEvent)
      .submitter as HTMLButtonElement | null;
    const decision = button?.value === "accepted" ? "accepted" : "rejected";
    if (!comment.trim()) {
      setError("Dodaj komentarz do decyzji.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (progress) {
        const result = await reviewMission(
          progress.id,
          decision,
          comment.trim(),
        );
        notify(
          decision === "accepted"
            ? `Misję zaakceptowano. Przyznano ${result.awarded_points} punktów.`
            : "Misję odrzucono. Autor może poprawić odpowiedź.",
        );
      } else {
        await reviewReport(report.id, decision, comment.trim());
        notify(
          decision === "accepted"
            ? "Zgłoszenie zaakceptowano."
            : "Zgłoszenie odrzucono.",
        );
      }
      done(report.id);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Nie udało się zapisać decyzji.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="panel review-card">
      <h2>{mission?.title || "Zgłoszenie informacji o miejscu"}</h2>
      {report.target.type === "place" && (
        <Link to={`/place/${encodeURIComponent(report.target.id)}`}>
          {mission?.place_name || "Zobacz miejsce"}
        </Link>
      )}
      {mission && <p>{mission.points} punktów po akceptacji.</p>}
      <p>{report.description}</p>
      {report.observations.map((item, index) => (
        <p key={index}>
          {item.attribute}: {String(item.value)}
        </p>
      ))}
      <p className="muted">
        Wysłano: {new Date(report.created_at).toLocaleString("pl-PL")}
      </p>
      <EvidencePhotos ids={report.photo_ids} />
      <form onSubmit={submit}>
        <fieldset disabled={busy} className="form-fields">
          <label className="field">
            Komentarz moderatora
            <textarea
              required
              maxLength={4000}
              rows={3}
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
          </label>
          {error && (
            <p className="warning-box" role="alert">
              {error}
            </p>
          )}
          <div className="actions">
            <button
              className="button primary"
              type="submit"
              value="accepted"
              disabled={busy}
            >
              Zaakceptuj
            </button>
            <button
              className="button subtle"
              type="submit"
              value="rejected"
              disabled={busy}
            >
              Odrzuć
            </button>
          </div>
        </fieldset>
      </form>
    </article>
  );
}

export function ReviewPage() {
  const { session } = useDemo();
  const [reports, setReports] = useState<Report[]>([]);
  const [progress, setProgress] = useState<MissionProgress[]>([]);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const moderator = session?.user.roles.includes("moderator");
  async function load() {
    setLoading(true);
    setError("");
    try {
      const [pendingReports, pendingMissions, catalog] = await Promise.all([
        listAll<Report>("/reports?mine=false&status=pending"),
        listAll<MissionProgress>("/missions/review-queue"),
        getMissions(),
      ]);
      setReports(
        pendingReports.filter((item) => item.author_id !== session?.user.id),
      );
      setProgress(pendingMissions);
      setMissions(catalog);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Nie udało się pobrać kolejki weryfikacji.",
      );
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    if (moderator) void load();
  }, [session?.user.id, moderator]);
  if (!moderator)
    return (
      <div className="page narrow">
        <PageHeading
          title="Weryfikacja"
          description="Ta strona jest dostępna dla moderatorów."
        />
        <Link className="button primary" to="/profile">
          Twój profil
        </Link>
      </div>
    );
  return (
    <div className="page narrow">
      <PageHeading
        title="Weryfikacja zgłoszeń i misji"
        description="Sprawdź opis i zdjęcia. Akceptacja misji przyznaje punkty jej autorowi."
      />
      <button
        className="button subtle"
        disabled={loading}
        onClick={() => void load()}
      >
        Odśwież kolejkę
      </button>
      {error && (
        <p className="warning-box" role="alert">
          {error}
        </p>
      )}
      {loading && <p role="status">Pobieranie kolejki…</p>}
      {!loading && !error && !reports.length && (
        <p>Brak zgłoszeń oczekujących na weryfikację.</p>
      )}
      {reports.map((report) => {
        const item = progress.find((value) => value.report_id === report.id);
        return (
          <ReviewCard
            key={report.id}
            report={report}
            progress={item}
            mission={missions.find((value) => value.id === item?.mission_id)}
            done={(id) =>
              setReports((items) => items.filter((value) => value.id !== id))
            }
          />
        );
      })}
    </div>
  );
}
