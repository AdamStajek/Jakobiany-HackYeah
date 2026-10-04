import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { PageHeading } from "../components/Common";
import { api, listAll, type PlaceSubmission } from "../data/api";
import { useDemo } from "../state/DemoContext";
import MapView from "../components/MapView";
import type { PlaceSummary } from "../data/types";

const noPlaces: PlaceSummary[] = [];

const placeCategories = [
  "Hotele",
  "Muzea",
  "Urzędy",
  "Sklepy spożywcze",
  "Biblioteki",
  "Kluby seniora",
];

const statuses = {
  pending: "Oczekuje na weryfikację",
  accepted: "Zaakceptowano",
  rejected: "Odrzucono",
};

export function NewPlacePage() {
  const { session, location } = useDemo();
  const [items, setItems] = useState<PlaceSubmission[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [coordinates, setCoordinates] = useState({ lat: "", lon: "" });
  const [picking, setPicking] = useState(false);
  useEffect(() => {
    if (success) document.getElementById("new-place-success")?.focus();
  }, [success]);
  useEffect(() => {
    if (picking)
      document
        .querySelector<HTMLElement>(".new-place-map .map-canvas")
        ?.focus();
  }, [picking]);
  useEffect(() => {
    if (!session) return;
    let active = true;
    listAll<PlaceSubmission>("/place-submissions?mine=true")
      .then((values) => {
        if (active)
          setItems(values.filter((item) => item.author_id === session.user.id));
      })
      .catch((reason: unknown) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Nie udało się pobrać zgłoszeń.",
          );
      });
    return () => {
      active = false;
    };
  }, [session?.user.id]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const item = await api<PlaceSubmission>("/place-submissions", {
        method: "POST",
        body: JSON.stringify({
          name: String(values.get("name")).trim(),
          category: String(values.get("category")).trim(),
          address: String(values.get("address")).trim(),
          description: String(values.get("description")).trim(),
          location: {
            lat: Number(values.get("lat")),
            lon: Number(values.get("lon")),
          },
        }),
      });
      setItems((current) => [item, ...current]);
      form.reset();
      setCoordinates({ lat: "", lon: "" });
      setPicking(false);
      setSuccess(
        "Zgłoszenie zapisane. Miejsce pojawi się w katalogu po zatwierdzeniu przez administratora.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Nie udało się zgłosić miejsca.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page narrow new-place-page">
      <PageHeading
        title="Dodaj nowe miejsce"
        description="Podaj dane miejsca. Administrator zweryfikuje zgłoszenie przed publikacją w katalogu."
      />
      {error && (
        <p role="alert" className="warning-box">
          {error}
        </p>
      )}
      {success && (
        <p role="status" id="new-place-success" tabIndex={-1}>
          {success}
        </p>
      )}
      {!session ? (
        <p>
          <Link to="/login?next=%2Fplaces%2Fnew" className="button primary">
            Zaloguj się, aby zgłosić miejsce
          </Link>
        </p>
      ) : (
        <>
          <form className="panel" onSubmit={submit}>
            <label className="field">
              Nazwa miejsca
              <input name="name" required maxLength={100} />
            </label>
            <label className="field">
              Kategoria
              <select name="category" required defaultValue="">
                <option value="" disabled>
                  Wybierz kategorię
                </option>
                {placeCategories.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Adres
              <input name="address" required maxLength={300} />
            </label>
            <p>Wskaż miejsce na mapie lub wpisz jego współrzędne.</p>
            <button
              type="button"
              className="button subtle"
              aria-expanded={picking}
              aria-controls="new-place-map"
              onClick={() => setPicking(!picking)}
            >
              {picking ? "Zamknij mapę" : "Wskaż miejsce na mapie"}
            </button>
            {picking && (
              <div className="new-place-map" id="new-place-map">
                <MapView
                  places={noPlaces}
                  userLocation={location}
                  onSelectPoint={({ lat, lon }) => {
                    setCoordinates({
                      lat: lat.toFixed(6),
                      lon: lon.toFixed(6),
                    });
                    setPicking(false);
                    requestAnimationFrame(() =>
                      document.getElementById("new-place-lat")?.focus(),
                    );
                  }}
                  onCancelSelection={() => {
                    setPicking(false);
                    requestAnimationFrame(() =>
                      document.getElementById("new-place-lat")?.focus(),
                    );
                  }}
                />
              </div>
            )}
            <label className="field">
              Szerokość geograficzna
              <input
                name="lat"
                id="new-place-lat"
                type="number"
                step="any"
                min={-90}
                max={90}
                required
                value={coordinates.lat}
                onChange={(event) =>
                  setCoordinates({ ...coordinates, lat: event.target.value })
                }
              />
            </label>
            <label className="field">
              Długość geograficzna
              <input
                name="lon"
                type="number"
                step="any"
                min={-180}
                max={180}
                required
                value={coordinates.lon}
                onChange={(event) =>
                  setCoordinates({ ...coordinates, lon: event.target.value })
                }
              />
            </label>
            <label className="field">
              Opis (opcjonalnie)
              <textarea name="description" maxLength={4000} />
            </label>
            <button className="button primary" disabled={busy}>
              {busy ? "Wysyłanie…" : "Wyślij do weryfikacji"}
            </button>
          </form>
          <h2>Twoje zgłoszenia miejsc</h2>
          {items.map((item) => (
            <article className="panel" key={item.id}>
              <h3>{item.name}</h3>
              <p>{statuses[item.status]}</p>
              {item.review_comment && (
                <p>Komentarz administratora: {item.review_comment}</p>
              )}
              {item.status === "accepted" && (
                <Link to={`/place/${encodeURIComponent(item.id)}`}>
                  Zobacz miejsce
                </Link>
              )}
            </article>
          ))}
        </>
      )}
    </div>
  );
}
