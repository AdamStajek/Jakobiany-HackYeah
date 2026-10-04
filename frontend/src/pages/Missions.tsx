import { translate } from "../i18n";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowRight,
  Star,
  Flag,
  MapPin,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Clock3,
  Award,
} from "lucide-react";
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
import { missionDistance, sortMissions } from "../data/missionSorting";
import MapView from "../components/MapView";

export const missionStatus = {
  in_progress: "W trakcie",
  pending: "Oczekuje na weryfikację",
  accepted: "Zaakceptowano",
  rejected: "Odrzucono",
};
const missionTitle = (mission: Mission) =>
  mission.target_type === "segment"
    ? mission.title.replace(/^Sprawdź(?: odcinek trasy)?:\s*/i, "")
    : mission.place_name;
export function MissionsPage() {
  const { activity, session, refreshActivity, location, setLocation } =
    useDemo();
  const [sort, setSort] = useState<"points" | "distance">("points");
  const [currentPage, setCurrentPage] = useState(1);
  const [locationError, setLocationError] = useState("");
  const [tab, setTab] = useState("available");
  const [missions, setMissions] = useState<Mission[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
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
  useEffect(() => setCurrentPage(1), [tab, sort, location?.lat, location?.lon]);
  const filtered = missions.filter(
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
  const shown = sortMissions(filtered, sort, location);
  const totalPages = Math.max(1, Math.ceil(shown.length / 10));
  const page = Math.min(currentPage, totalPages);
  const pageWindowStart = Math.floor((page - 1) / 5) * 5 + 1;
  const visiblePages = Array.from(
    { length: Math.min(5, totalPages - pageWindowStart + 1) },
    (_, index) => pageWindowStart + index,
  );
  function selectSort(value: "points" | "distance") {
    setSort(value);
    setLocationError("");
    if (value !== "distance" || location) return;
    if (!navigator.geolocation) {
      setLocationError("Przeglądarka nie obsługuje lokalizacji.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) =>
        setLocation({ lat: coords.latitude, lon: coords.longitude }),
      () =>
        setLocationError(
          "Udostępnij lokalizację, aby sortować misje według odległości.",
        ),
      { timeout: 10000, maximumAge: 60000 },
    );
  }
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
          <p>Uzupełnij informacje o miejscach w okolicy i pomóż innym.</p>
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
      <label className="field search-sort">
        Sortuj misje
        <select
          value={sort}
          onChange={(event) =>
            selectSort(event.target.value as "points" | "distance")
          }
        >
          <option value="points">Punkty: od największej liczby</option>
          <option value="distance">Odległość: od najbliższej</option>
        </select>
      </label>
      {sort === "distance" && !location && (
        <p className="muted" role="status">
          {locationError || "Oczekiwanie na lokalizację…"}
        </p>
      )}
      {error && (
        <p className="warning-box" role="alert">
          {error}
        </p>
      )}
      {loading && <p role="status">Pobieranie misji…</p>}
      {shown.slice((page - 1) * 10, page * 10).map((mission) => {
        const progress = activity.items.find(
          (item) => item.mission_id === mission.id,
        );
        const distance = missionDistance(mission, location);
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
              <h2>{missionTitle(mission)}</h2>
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
              {mission.address && (
                <p className="muted mission-address">
                  <MapPin size={15} aria-hidden="true" />
                  {mission.address_is_nearest ? "Najbliższy adres: " : ""}
                  {mission.address}
                </p>
              )}
              {Number.isFinite(distance) && (
                <p className="muted mission-distance">
                  {distance < 1000
                    ? `${Math.round(distance)} m od Ciebie`
                    : `${(distance / 1000).toFixed(1)} km od Ciebie`}
                </p>
              )}
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
      {totalPages > 1 && (
        <nav className="results-pagination" aria-label="Strony misji">
          <button
            className="button subtle"
            aria-label="Pierwsza strona"
            onClick={() => setCurrentPage(1)}
            disabled={page === 1}
          >
            <ChevronsLeft size={18} />
          </button>
          <button
            className="button subtle"
            aria-label="Poprzednie 5 stron"
            onClick={() => setCurrentPage(Math.max(1, pageWindowStart - 5))}
            disabled={pageWindowStart === 1}
          >
            <ChevronLeft size={18} />
          </button>
          {visiblePages.map((number) => (
            <button
              key={number}
              className={`button subtle ${number === page ? "active" : ""}`}
              aria-current={number === page ? "page" : undefined}
              onClick={() => setCurrentPage(number)}
            >
              {number}
            </button>
          ))}
          <button
            className="button subtle"
            aria-label="Następne 5 stron"
            onClick={() =>
              setCurrentPage(Math.min(totalPages, pageWindowStart + 5))
            }
            disabled={pageWindowStart + 5 > totalPages}
          >
            <ChevronRight size={18} />
          </button>
          <button
            className="button subtle"
            aria-label="Ostatnia strona"
            onClick={() => setCurrentPage(totalPages)}
            disabled={page === totalPages}
          >
            <ChevronsRight size={18} />
          </button>
        </nav>
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
  const { activity, session, refreshActivity, location, setLocation } =
    useDemo();
  const [mission, setMission] = useState<Mission | null>(null);
  const [current, setCurrent] = useState<MissionProgress | null>(null);
  const [metricValue, setMetricValue] = useState<Fact["value"]>(null);
  useEffect(() => setMetricValue(null), [id]);
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [locationMessage, setLocationMessage] = useState("");
  useEffect(() => {
    if (location) return;
    if (!navigator.geolocation) {
      setLocationMessage("Przeglądarka nie obsługuje lokalizacji.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) =>
        setLocation({ lat: coords.latitude, lon: coords.longitude }),
      () =>
        setLocationMessage("Udostępnij lokalizację, aby pokazać ją na mapie."),
      { timeout: 10000, maximumAge: 60000 },
    );
  }, [location, setLocation]);
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
          (mission && missionTitle(mission)) ||
          (error ? "Nie udało się pobrać misji" : "Pobieranie misji…")
        }
        description={
          mission
            ? `${mission.time_minutes} ${translate("minut")} · ${mission.points} ${translate("punktów po zatwierdzeniu")}`
            : ""
        }
      />
      {error && (
        <p className="warning-box" role="alert">
          {error}
        </p>
      )}
      {mission && (
        <div className="panel mission-detail-panel">
          <div className="mission-facts">
            <span>
              <Clock3 size={17} /> Około {mission.time_minutes} min
            </span>
            <span>
              <Award size={17} /> {mission.points} pkt po zatwierdzeniu
            </span>
          </div>
          <p>{mission.description}</p>
          <p className="mission-detail-address">
            <strong>
              {mission.target_type === "segment"
                ? "Odcinek"
                : mission.address_is_nearest
                  ? "Najbliższy adres"
                  : "Adres"}
            </strong>
            <span>
              {mission.target_type === "segment"
                ? mission.place_name
                : mission.address || "Adres niedostępny"}
            </span>
          </p>
          {location &&
            mission.location &&
            Number.isFinite(missionDistance(mission, location)) && (
              <p className="mission-distance-detail">
                <MapPin size={17} />{" "}
                {missionDistance(mission, location) < 1000
                  ? `${Math.round(missionDistance(mission, location))} m od Ciebie`
                  : `${(missionDistance(mission, location) / 1000).toFixed(1)} km od Ciebie`}
              </p>
            )}
          {mission.location && (
            <>
              {!location && (
                <p className="muted" role="status">
                  {locationMessage || "Ustalanie Twojej lokalizacji…"}
                </p>
              )}
              <MapView
                places={
                  mission.target_type === "segment"
                    ? []
                    : [
                        {
                          id: mission.place_id,
                          name: mission.place_name,
                          category: "",
                          address: mission.address,
                          address_is_nearest: mission.address_is_nearest,
                          location: mission.location,
                          distance_m: null,
                        },
                      ]
                }
                endpoints={
                  mission.target_type === "segment"
                    ? [
                        {
                          ...mission.location,
                          label: "Miejsce misji",
                        },
                      ]
                    : []
                }
                userLocation={location}
                showMobilityList={false}
              />
            </>
          )}
          <p>
            <strong>
              Informacja do potwierdzenia:{" "}
              {labels[mission.attribute] || mission.attribute}
            </strong>
          </p>
          {mission.target_type !== "segment" && (
            <Link
              className="button subtle"
              to={`/place/${encodeURIComponent(mission.place_id)}`}
            >
              Zobacz miejsce <MapPin size={18} />
            </Link>
          )}
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
