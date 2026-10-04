import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { interpretSearch, type SearchProposal } from "../data/api";
import { useDemo } from "../state/DemoContext";

export default function AISearch({
  mode,
  onApply,
}: {
  mode: "places" | "routes";
  onApply: (proposal: SearchProposal) => void;
}) {
  const { constraints, setConstraints, profile, notify } = useDemo();
  const [prompt, setPrompt] = useState("");
  const [proposal, setProposal] = useState<SearchProposal | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const prepareButton = useRef<HTMLButtonElement>(null);

  async function search() {
    setLoading(true);
    setError("");
    setProposal(null);
    try {
      setProposal(await interpretSearch(mode, prompt.trim(), constraints));
    } catch {
      setError("Nie udało się przygotować wyszukiwania AI. Spróbuj ponownie.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel" aria-label="Wyszukiwanie AI">
      {profile ? (
        <button
          type="button"
          className="button subtle"
          onClick={() => {
            setConstraints({ ...profile.constraints });
            setProposal(null);
            notify("Zastosowano ustawienia z profilu.");
          }}
        >
          Użyj ustawień z profilu
        </button>
      ) : (
        <Link className="button subtle" to="/profile/setup">
          Ustaw preferencje w profilu
        </Link>
      )}
      <h2>Wyszukiwanie AI</h2>
      <label className="field">
        Opisz, czego szukasz
        <textarea
          value={prompt}
          maxLength={4000}
          disabled={loading}
          placeholder={
            mode === "places"
              ? "Znajdź kawiarnię bez schodów z dostępną toaletą"
              : "Z Rynku Głównego na Wawel, bez schodów"
          }
          onChange={(event) => {
            setPrompt(event.target.value);
            setProposal(null);
          }}
        />
      </label>
      <button
        ref={prepareButton}
        type="button"
        className="button primary"
        disabled={loading || !prompt.trim()}
        onClick={search}
      >
        {loading ? "Przygotowywanie…" : "Przygotuj wyszukiwanie"}
      </button>
      <div aria-live="polite">
        {loading && <p>Przygotowywanie wyszukiwania…</p>}
        {error && <p role="alert">{error}</p>}
        {proposal && (
          <>
            <p>{proposal.summary}</p>
            {proposal.query && <p>Fraza: {proposal.query}</p>}
            {proposal.origin_query && <p>Skąd: {proposal.origin_query}</p>}
            {proposal.destination_query && (
              <p>Dokąd: {proposal.destination_query}</p>
            )}
            {proposal.questions.map((question, index) => (
              <p key={index}>{question}</p>
            ))}
            <p className="small">
              Zastosuj propozycję i sprawdź filtry
              {mode === "routes"
                ? " oraz wybierz punkty z wyników wyszukiwania"
                : ""}
              . Możesz je poprawić.
            </p>
            <button
              type="button"
              className="button primary"
              onClick={() => {
                setConstraints(proposal.constraints);
                onApply(proposal);
                setProposal(null);
                prepareButton.current?.focus();
              }}
            >
              Zastosuj wyszukiwanie
            </button>
          </>
        )}
      </div>
    </section>
  );
}
