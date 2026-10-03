export function EvidencePhotos({ ids }: { ids: string[] }) {
  if (!ids.length) return null;
  return (
    <div className="evidence-photos">
      {ids.map((id) => (
        <a
          key={id}
          href={`/api/v1/photos/${encodeURIComponent(id)}/content`}
          target="_blank"
          rel="noreferrer"
        >
          <img
            src={`/api/v1/photos/${encodeURIComponent(id)}/content`}
            alt="Zdjęcie dołączone do zgłoszenia"
          />
        </a>
      ))}
    </div>
  );
}
