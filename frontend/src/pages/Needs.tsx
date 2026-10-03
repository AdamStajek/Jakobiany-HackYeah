import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Sparkles, ArrowRight, Check } from "lucide-react";
import { useDemo } from "../state/DemoContext";
import { PageHeading } from "../components/Common";
import Numeric from "../components/Numeric";
import type { Constraints } from "../data/types";
export function NeedsPage() {
  const { constraints, setConstraints } = useDemo();
  const [step, setStep] = useState(1);
  const [description, setDescription] = useState("");
  const [draft, setDraft] = useState<Constraints>({ ...constraints });
  function next(e: FormEvent) {
    e.preventDefault();
    setStep(2);
  }
  return (
    <div className="page narrow">
      <PageHeading
        eyebrow="TWOJE TEMPO, TWOJE POTRZEBY"
        title="Twój profil potrzeb"
        description="Nie musisz podawać diagnozy. Wybierz tylko to, co ułatwi Ci drogę."
      />
      <ol className="stepper">
        {["Opisz potrzeby", "Sprawdź ustawienia", "Gotowe"].map((s, i) => (
          <li className={step === i + 1 ? "active" : ""} key={s}>
            <span>{i + 1}</span>
            {s}
          </li>
        ))}
      </ol>
      <div className="panel needs-panel">
        {step === 1 ? (
          <form onSubmit={next}>
            <div className="callout">
              <Sparkles />
              <p>
                W demonstracji opis nie jest analizowany przez AI. W kolejnym
                kroku samodzielnie ustawisz potrzeby.
              </p>
            </div>
            <label className="field">
              Opisz swoje potrzeby
              <textarea
                rows={5}
                maxLength={4000}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Np. unikam schodów i potrzebuję ławki co 300 metrów."
              />
            </label>
            <p className="muted">
              Możesz też pominąć opis i wybrać wymagania z listy.
            </p>
            <button className="button primary">
              Dalej <ArrowRight size={18} />
            </button>
          </form>
        ) : step === 2 ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setConstraints(draft);
              setStep(3);
            }}
          >
            <h2>Wybierz i potwierdź swoje potrzeby</h2>
            <div className="form-grid">
              <Numeric
                label="Maksymalna liczba stopni"
                value={draft.max_steps}
                onChange={(v) =>
                  setDraft({
                    ...draft,
                    max_steps: v,
                    require_step_free_access:
                      v !== null && v > 0
                        ? null
                        : draft.require_step_free_access,
                  })
                }
              />
              <Numeric
                label="Maksymalne nachylenie (%)"
                value={draft.max_slope_percent}
                onChange={(v) => setDraft({ ...draft, max_slope_percent: v })}
              />
              <Numeric
                label="Maksymalna wysokość progu (cm)"
                value={draft.max_threshold_cm}
                onChange={(v) => setDraft({ ...draft, max_threshold_cm: v })}
              />
              <Numeric
                label="Minimalna szerokość wejścia (cm)"
                min={1}
                value={draft.min_entrance_width_cm}
                onChange={(v) =>
                  setDraft({ ...draft, min_entrance_width_cm: v })
                }
              />
              <Numeric
                label="Odpoczynek co najwyżej co (m)"
                min={1}
                value={draft.max_distance_without_rest_m}
                onChange={(v) =>
                  setDraft({ ...draft, max_distance_without_rest_m: v })
                }
              />
              <label className="field">
                Toaleta dostępna
                <select
                  aria-label="Toaleta dostępna"
                  value={
                    draft.require_accessible_toilet === null
                      ? "null"
                      : String(draft.require_accessible_toilet)
                  }
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      require_accessible_toilet:
                        e.target.value === "null"
                          ? null
                          : e.target.value === "true",
                    })
                  }
                >
                  <option value="null">Nie określam</option>
                  <option value="true">Wymagana</option>
                  <option value="false">Niewymagana</option>
                </select>
              </label>
            </div>
            <label className="check-field">
              <input
                type="checkbox"
                checked={draft.require_step_free_access === true}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    require_step_free_access: e.target.checked ? true : null,
                    max_steps: e.target.checked ? 0 : draft.max_steps,
                  })
                }
              />
              Potrzebuję wejścia bez stopni
            </label>
            <label className="check-field">
              <input
                type="checkbox"
                checked={draft.allowed_surfaces !== null}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    allowed_surfaces: e.target.checked
                      ? ["paved", "asphalt"]
                      : null,
                  })
                }
              />
              Tylko utwardzona nawierzchnia lub asfalt
            </label>
            <div className="actions">
              <button
                type="button"
                className="button subtle"
                onClick={() => setStep(1)}
              >
                Wstecz
              </button>
              <button className="button primary">Zapisz profil</button>
            </div>
          </form>
        ) : (
          <div className="success-state">
            <span className="success-icon">
              <Check size={36} />
            </span>
            <h2>Twoje potrzeby są zapisane</h2>
            <p>
              Wyniki będą dopasowane do tych ustawień w tej sesji
              demonstracyjnej.
            </p>
            <div className="actions">
              <Link className="button primary" to="/search">
                Znajdź miejsce
              </Link>
              <Link className="button subtle" to="/route">
                Wyznacz trasę
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
