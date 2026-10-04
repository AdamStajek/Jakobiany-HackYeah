import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { PageHeading } from "../components/Common";
import MapView from "../components/MapView";
import { useDemo } from "../state/DemoContext";
import {
  api,
  type PlaceSubmission,
  listAll,
} from "../data/api";
import type { PlaceSummary } from "../data/types";

const noPlaces: PlaceSummary[] = [];

function PlaceSubmissionCard({
  item,
  done,
}: {
  item: PlaceSubmission;
  done: () => void;
}) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [location, setLocation] = useState(item.location);
  const [pickingLocation, setPickingLocation] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const decision = (event.nativeEvent as SubmitEvent).submitter?.getAttribute(
      "value",
    );
    if (
      !comment.trim() ||
      !decision ||
      (decision === "accepted" && !location)
    )
      return;
    setBusy(true);
    setError("");
    try {
      await api(`/place-submissions/${encodeURIComponent(item.id)}/review`, {
        method: "POST",
        body: JSON.stringify({
          decision,
          comment: comment.trim(),
          ...(decision === "accepted" && location ? { location } : {}),
        }),
      });
      done();
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
      <h2>{item.name}</h2>
      <p>
        {item.category}
        {item.address ? ` · ${item.address}` : ""}
      </p>
      {location ? (
        <>
          <p>Współrzędne: {location.lat}, {location.lon}</p>
          <a
            href={`https://www.openstreetmap.org/?mlat=${location.lat}&mlon=${location.lon}#map=18/${location.lat}/${location.lon}`}
            target="_blank"
            rel="noreferrer"
          >Sprawdź na mapie</a>
        </>
      ) : (
        <p>Przed zatwierdzeniem wskaż położenie miejsca na mapie.</p>
      )}
      <button
        type="button"
        className="button subtle"
        onClick={() => setPickingLocation(!pickingLocation)}
      >
        {pickingLocation ? "Zamknij mapę" : location ? "Zmień położenie na mapie" : "Wskaż położenie na mapie"}
      </button>
      {pickingLocation && (
        <MapView
          places={noPlaces}
          onSelectPoint={(point) => {
            setLocation(point);
            setPickingLocation(false);
          }}
          onCancelSelection={() => setPickingLocation(false)}
        />
      )}
      {item.description && <p>{item.description}</p>}
      <form onSubmit={submit}>
        <label className="field">
          Komentarz administratora
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            required
            maxLength={4000}
          />
        </label>
        {error && (
          <p role="alert" className="warning-box">
            {error}
          </p>
        )}
        <button
          className="button primary"
          value="accepted"
          disabled={busy || !comment.trim() || !location}
        >
          Zatwierdź miejsce
        </button>
        <button
          className="button subtle"
          value="rejected"
          disabled={busy || !comment.trim()}
        >
          Odrzuć
        </button>
      </form>
    </article>
  );
}

export function ReviewPage() {
  const { session } = useDemo();
  const [places, setPlaces] = useState<PlaceSubmission[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const moderator = session?.user.roles.includes("moderator");
  async function load() {
    setLoading(true);
    setError("");
    try {
      const pendingPlaces = await listAll<PlaceSubmission>("/place-submissions");
      setPlaces(
        pendingPlaces.filter((item) => item.author_id !== session?.user.id),
      );
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
        title="Weryfikacja nowych miejsc"
        description="Administratorzy zatwierdzają zgłoszenia nowych miejsc. Misje weryfikuje model AI."
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
      {!loading && !error && !places.length && (
        <p>Brak miejsc oczekujących na weryfikację.</p>
      )}
      {places.map((item) => (
        <PlaceSubmissionCard
          key={item.id}
          item={item}
          done={() =>
            setPlaces((current) =>
              current.filter((value) => value.id !== item.id),
            )
          }
        />
      ))}
    </div>
  );
}
