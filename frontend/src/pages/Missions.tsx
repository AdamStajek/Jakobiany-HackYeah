import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, Star, Flag, MapPin, ChevronLeft } from "lucide-react";
import { useDemo } from "../state/DemoContext";
import { PageHeading } from "../components/Common";
import {
  getMission,
  getMissions,
  startMission,
  submitMission,
  withPhoto,
  type Mission,
  type MissionProgress,
} from "../data/api";
import { MetricInput } from "../components/MetricInput";
import type { Fact } from "../data/types";
import { labels } from "../data/mock";

export const missionStatus = {
  in_progress: "W trakcie",
  pending: "Oczekuje na weryfikację",
  accepted: "Zaakceptowano",
  rejected: "Odrzucono",
};
export function MissionsPage() {
  const { activity, session, refreshActivity } = useDemo();
  const [offset, setOffset] = useState(0);
  const [more, setMore] = useState(true);
  const [tab, setTab] = useState("available");
  const [missions, setMissions] = useState<Mission[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setOffset(0);
    setMore(true);
    getMissions()
      .then((items) => {
        if (active) setMissions(items);
      })
      .catch((reason: unknown) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Nie udało się pobrać misji.",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    if (session)
      refreshActivity().catch((reason: unknown) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Nie udało się pobrać postępów.",
          );
      });
    return () => {
      active = false;
    };
  }, [session?.user.id]);
  const shown = missions.filter(
    (mission) =>
      (tab === "available" &&
        mission.available &&
        !activity.items.some(
          (item) =>
            item.mission_id === mission.id &&
            ["pending", "accepted"].includes(item.status),
        )) ||
      (tab === "completed" &&
        activity.items.some(
          (item) =>
            item.mission_id === mission.id && item.status === "accepted",
        )) ||
      (tab === "progress" &&
        activity.items.some((item) => item.mission_id === mission.id)),
  );
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
        <span>Saldo: {activity.points} pkt</span>
      </div>
      <div className="tabs" role="group" aria-label="Wybierz widok misji">
        <button
          className={tab === "available" ? "active" : ""}
          aria-pressed={tab === "available"}
          onClick={() => setTab("available")}
        >
          Dostępne misje
        </button>
        <button
          className={tab === "progress" ? "active" : ""}
          aria-pressed={tab === "progress"}
          onClick={() => setTab("progress")}
        >
          Moje postępy
        </button>
        <button
          className={tab === "completed" ? "active" : ""}
          aria-pressed={tab === "completed"}
          onClick={() => setTab("completed")}
        >
          Wykonane misje
        </button>
      </div>
      {error && (
        <p className="warning-box" role="alert">
          {error}
        </p>
      )}
      {loading && <p role="status">Pobieranie misji…</p>}
      {shown.map((mission) => {
        const progress = activity.items.find(
          (item) => item.mission_id === mission.id,
        );
        return (
          <Link
            className="panel mission-card"
            key={mission.id}
            to={`/missions/${encodeURIComponent(mission.id)}`}
          >
            <span className="option-icon">
              <MapPin />
            </span>
            <div>
              <h2>{mission.title}</h2>
              <p>
                {labels[mission.attribute] || mission.attribute} ·{" "}
                {
                  {
                    1: "Zgłoszone do weryfikacji",
                    2: "Brakujące dane",
                    3: "Niepewne dane",
                  }[mission.priority]
                }
              </p>
              <p className="muted">
                Około {mission.time_minutes} minut ·{" "}
                {progress ? missionStatus[progress.status] : "Dostępna"}
              </p>
              <strong className="points">
                {progress?.status === "accepted"
                  ? `${progress.awarded_points} pkt przyznano`
                  : `+${mission.points} pkt po zatwierdzeniu`}
              </strong>
            </div>
            <ArrowRight />
          </Link>
        );
      })}
      {tab === "available" && more && (
        <button
          className="button subtle"
          disabled={loading}
          onClick={async () => {
            setLoading(true);
            try {
              const items = await getMissions(undefined, offset + 100);
              const fresh = items.filter(
                (item) => !missions.some((old) => old.id === item.id),
              );
              setMore(fresh.length > 0);
              setOffset(offset + 100);
              setMissions((old) =>
                [...old, ...fresh].sort((a, b) => a.priority - b.priority),
              );
            } catch {
              setError("Nie udało się pobrać kolejnych misji.");
            } finally {
              setLoading(false);
            }
          }}
        >
          Wczytaj kolejne miejsca
        </button>
      )}
      {!loading && !shown.length && (
        <div className="empty-state">
          <Flag />
          <h2>
            {tab === "available"
              ? "Brak dostępnych misji"
              : "Tu pojawią się Twoje misje"}
          </h2>
          <p>Wybierz zadanie z zakładki „Dostępne misje”.</p>
        </div>
      )}
      <p className="muted">
        Punkty są przyznawane po akceptacji odpowiedzi przez model lub
        moderatora. Postępy i nagrody są zapisywane na Twoim koncie.
      </p>
      {!session && (
        <Link className="button primary" to="/login?next=%2Fmissions">
          Zaloguj się, aby rozpocząć misję
        </Link>
      )}
    </div>
  );
}

export function MissionPage() {
  const { id } = useParams();
  const { activity, session, refreshActivity } = useDemo();
  const [mission, setMission] = useState<Mission | null>(null);
  const [current, setCurrent] = useState<MissionProgress | null>(null);
  const [metricValue, setMetricValue] = useState<Fact["value"]>(null);
  useEffect(() => setMetricValue(null), [id]);
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    if (id)
      getMission(id)
        .then((item) => {
          if (active) setMission(item);
        })
        .catch((reason: unknown) => {
          if (active)
            setError(
              reason instanceof Error
                ? reason.message
                : "Nie udało się pobrać misji.",
            );
        });
    if (session)
      refreshActivity().catch((reason: unknown) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Nie udało się pobrać postępu misji.",
          );
      });
    return () => {
      active = false;
    };
  }, [id, session?.user.id]);
  useEffect(() => {
    const progress =
      activity.items.find((item) => item.mission_id === id) || null;
    setCurrent(progress);
  }, [id, activity.items]);
  async function start() {
    if (!mission || busy) return;
    setBusy(true);
    setError("");
    try {
      setCurrent(await startMission(mission.id));
      await refreshActivity();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Nie udało się rozpocząć misji.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!mission || busy) return;
    setBusy(true);
    setError("");
    try {
      setCurrent(
        await withPhoto(
          photo,
          (ids) =>
            submitMission(
              mission.id,
              ids,
              metricValue === null
                ? []
                : [{ attribute: mission.attribute, value: metricValue }],
            ),
          {
            address: mission.address || mission.place_name,
            metric: mission.attribute,
          },
        ),
      );
      setPhoto(null);
      await refreshActivity();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Nie udało się wysłać odpowiedzi.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page narrow">
      <Link className="back-link" to="/missions">
        <ChevronLeft size={18} />
        Wszystkie misje
      </Link>
      <PageHeading
        title={
          mission?.title ||
          (error ? "Nie udało się pobrać misji" : "Pobieranie misji…")
        }
        description={
          mission
            ? `${mission.time_minutes} minut · ${mission.points} punktów po zatwierdzeniu`
            : ""
        }
      />
      {error && (
        <p className="warning-box" role="alert">
          {error}
        </p>
      )}
      {mission && (
        <div className="panel">
          <p>{mission.description}</p>
          <p>
            <strong>Adres:</strong> {mission.address || "Adres niedostępny"}
          </p>
          <p>
            <strong>
              Do sprawdzenia: {labels[mission.attribute] || mission.attribute}
            </strong>
          </p>
          <Link
            className="button subtle"
            to={`/place/${encodeURIComponent(mission.place_id)}`}
          >
            Zobacz miejsce <MapPin size={18} />
          </Link>
          {!session ? (
            <Link
              className="button primary"
              to={`/login?next=${encodeURIComponent(`/missions/${mission.id}`)}`}
            >
              Zaloguj się, aby rozpocząć misję
            </Link>
          ) : !current ? (
            <button className="button primary" disabled={busy} onClick={start}>
              {busy ? "Rozpoczynanie…" : "Rozpocznij misję"}
            </button>
          ) : (
            <>
              <p
                className={`status ${current.status === "accepted" ? "good" : "warning"}`}
                role="status"
              >
                {missionStatus[current.status]} · {current.awarded_points}{" "}
                naliczonych punktów
              </p>
              {current.answer && <p>Twoja odpowiedź: {current.answer}</p>}
              <p className="muted">
                Aktualizacja:{" "}
                {new Date(current.updated_at).toLocaleString("pl-PL")}
              </p>
              {current.review_comment && (
                <p>Wynik weryfikacji: {current.review_comment}</p>
              )}
              {current.status === "pending" && (
                <p>
                  Odpowiedź wysłano do weryfikacji. Po akceptacji otrzymasz{" "}
                  {mission.points} punktów.
                </p>
              )}
              {(current.status === "in_progress" ||
                current.status === "rejected") && (
                <form onSubmit={submit}>
                  <fieldset disabled={busy} className="form-fields">
                    <MetricInput
                      attribute={mission.attribute}
                      value={metricValue}
                      onChange={setMetricValue}
                    />
                    <label className="field">
                      Zdjęcie (opcjonalne)
                      <input
                        type="file"
                        aria-label="Zdjęcie (opcjonalne)"
                        aria-describedby="mission-photo-help"
                        accept="image/jpeg,image/png,image/webp"
                        onChange={(event) =>
                          setPhoto(event.target.files?.[0] || null)
                        }
                      />
                      <small id="mission-photo-help">
                        JPEG, PNG lub WebP, do 10 MiB. Model sprawdzi na zdjęciu
                        cechę wskazaną w misji.
                      </small>
                    </label>
                    <button className="button primary" disabled={busy}>
                      {busy
                        ? "Wysyłanie…"
                        : current.status === "rejected"
                          ? "Wyślij poprawioną odpowiedź"
                          : "Wyślij odpowiedź do weryfikacji"}
                    </button>
                  </fieldset>
                </form>
              )}
              <button
                type="button"
                className="text-button"
                disabled={busy}
                onClick={() => {
                  setError("");
                  refreshActivity().catch((reason: unknown) =>
                    setError(
                      reason instanceof Error
                        ? reason.message
                        : "Nie udało się odświeżyć postępu.",
                    ),
                  );
                }}
              >
                Odśwież status
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
