import { useState } from "react";
import { interpretSearch, type SearchProposal } from "../data/api";
import { useDemo } from "../state/DemoContext";

export default function AISearch({
  mode,
  onApply,
}: {
  mode: "places" | "routes";
  onApply: (proposal: SearchProposal) => void;
}) {
  const { constraints, setConstraints } = useDemo();
  const [prompt, setPrompt] = useState("");
  const [proposal, setProposal] = useState<SearchProposal | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function search() {
    setLoading(true);
    setError("");
    setProposal(null);
    try {
      const nextProposal = await interpretSearch(
        mode,
        prompt.trim(),
        constraints,
      );
      setConstraints(nextProposal.constraints);
      onApply(nextProposal);
      setProposal(nextProposal);
    } catch {
      setError("Nie udało się przygotować wyszukiwania AI. Spróbuj ponownie.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <details className="panel ai-search">
      <summary>Wyszukiwanie AI — opisz swoje potrzeby</summary>
      <div className="ai-search-content">
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
          type="button"
          className="button primary"
          disabled={loading || !prompt.trim()}
          onClick={search}
        >
          {loading ? "Szukam…" : "Szukaj"}
        </button>
        <div aria-live="polite">
          {loading && <p>Przygotowuję wyszukiwanie…</p>}
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
                Wyszukiwanie zostało zastosowane. Możesz poprawić filtry i
                wyniki.
                {mode === "routes"
                  ? " Wybierz punkty trasy z podpowiedzi."
                  : ""}
              </p>
            </>
          )}
        </div>
      </div>
    </details>
  );
}
