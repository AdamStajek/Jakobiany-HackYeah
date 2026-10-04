import { useEffect, useState } from "react";
import { api, type Photo } from "../data/api";

export function EvidencePhotos({
  ids,
  description,
}: {
  ids: string[];
  description?: string | null;
}) {
  if (!ids.length) return null;
  return (
    <div className="evidence-photos">
      {ids.map((id) => (
        <EvidencePhoto key={id} id={id} description={description} />
      ))}
    </div>
  );
}

function EvidencePhoto({
  id,
  description,
}: {
  id: string;
  description?: string | null;
}) {
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const result = await api<Photo>(`/photos/${encodeURIComponent(id)}`);
        if (!active) return;
        setPhoto(result);
        setError(false);
        if (result.status === "processing") timer = setTimeout(refresh, 3000);
      } catch {
        if (active) {
          setError(true);
          timer = setTimeout(refresh, 5000);
        }
      }
    };
    void refresh();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [id]);
  if (error) return <p role="status">Nie udało się pobrać zdjęcia.</p>;
  if (!photo || photo.status === "processing")
    return <p role="status">Przetwarzanie zdjęcia…</p>;
  if (photo.status === "rejected" || !photo.preview_url)
    return <p>Nie udało się bezpiecznie przetworzyć zdjęcia.</p>;
  return (
    <a href={photo.preview_url} target="_blank" rel="noreferrer">
      <img
        src={photo.preview_url}
        alt={`Zdjęcie dołączone do zgłoszenia${description?.trim() ? ` — ${description.trim()}` : ""}`}
      />
    </a>
  );
}
