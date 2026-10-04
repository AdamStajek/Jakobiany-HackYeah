import { useEffect, useState } from "react";
import { PageHeading } from "../components/Common";

export function Settings() {
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
        title="Ustawienia"
        description="Dopasuj wygląd strony do swoich potrzeb."
      />
      <section className="panel">
        <h2>Dostępność ekranu</h2>
        <label className="check-field">
          <input
            type="checkbox"
            checked={large}
            onChange={(event) => setLarge(event.target.checked)}
          />
          Większy tekst
        </label>
        <label className="check-field">
          <input
            type="checkbox"
            checked={contrast}
            onChange={(event) => setContrast(event.target.checked)}
          />
          Zwiększony kontrast
        </label>
      </section>
    </div>
  );
}
