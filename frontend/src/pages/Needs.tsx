import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Sparkles, ArrowRight, Check } from "lucide-react";
import { useDemo } from "../state/DemoContext";
import { PageHeading } from "../components/Common";
import Numeric from "../components/Numeric";
import { interpretNeeds } from "../data/api";
import type { Constraints } from "../data/types";
export function NeedsPage() {
  const { constraints, saveProfile, profile, session } = useDemo();
  const [step, setStep] = useState(1);
  const [description, setDescription] = useState(profile?.description || "");
  const [draft, setDraft] = useState<Constraints>({ ...constraints });
  const [interpreting, setInterpreting] = useState(false);
  const [interpretError, setInterpretError] = useState("");
  const [summary, setSummary] = useState("");
  const [questions, setQuestions] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const panel = useRef<HTMLDivElement>(null);
  const previousStep = useRef(step);
  useEffect(() => {
    if (step !== previousStep.current)
      panel.current?.querySelector<HTMLElement>("h2, textarea")?.focus();
    previousStep.current = step;
  }, [step]);
  async function next(e: FormEvent) {
    e.preventDefault();
    if (!description.trim()) {
      setStep(2);
      return;
    }
    setInterpreting(true);
    setInterpretError("");
    try {
      const result = await interpretNeeds(description.trim());
      setDraft(result.constraints);
      setSummary(result.summary);
      setQuestions(result.questions);
      setStep(2);
    } catch {
      setInterpretError(
        "Nie udało się odczytać opisu potrzeb. Spróbuj ponownie lub ustaw wymagania ręcznie.",
      );
    } finally {
      setInterpreting(false);
    }
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
          <li
            className={step === i + 1 ? "active" : ""}
            key={s}
            aria-current={step === i + 1 ? "step" : undefined}
          >
            <span>{i + 1}</span>
            {s}
          </li>
        ))}
      </ol>
      <div className="panel needs-panel" ref={panel}>
        {step === 1 ? (
          <form onSubmit={next}>
            <div className="callout">
              <Sparkles />
              <p>
                Opisz potrzeby, a zaproponujemy ustawienia. W kolejnym kroku
                sprawdzisz i zatwierdzisz wymagania.
              </p>
            </div>
            <label className="field">
              Opisz swoje potrzeby
              <textarea
                rows={5}
                disabled={interpreting}
                maxLength={4000}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Np. unikam schodów i potrzebuję ławki co 300 metrów."
              />
            </label>
            <p className="muted">
              Możesz też pominąć opis i wybrać wymagania z listy.
            </p>
            <button className="button primary" disabled={interpreting}>
              {interpreting ? "Odczytywanie potrzeb…" : "Dalej"}{" "}
              <ArrowRight size={18} />
            </button>
            {interpretError && <p role="alert">{interpretError}</p>}
            <button
              type="button"
              className="button subtle"
              disabled={interpreting}
              onClick={() => {
                setSummary("");
                setQuestions([]);
                setStep(2);
              }}
            >
              Wybierz potrzeby ręcznie
            </button>
          </form>
        ) : step === 2 ? (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setSaving(true);
              setSaveError("");
              try {
                await saveProfile(description, draft);
                setStep(3);
              } catch (reason) {
                setSaveError(
                  reason instanceof Error
                    ? reason.message
                    : "Nie udało się zapisać profilu.",
                );
              } finally {
                setSaving(false);
              }
            }}
          >
            <fieldset disabled={saving} className="form-fields">
              <h2 tabIndex={-1}>Wybierz i potwierdź swoje potrzeby</h2>
              {saveError && (
                <p className="warning-box" role="alert">
                  {saveError}
                </p>
              )}
              {summary && <p>{summary}</p>}
              {questions.map((question, index) => (
                <p className="warning-box" key={index}>
                  {question}
                </p>
              ))}
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
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={draft.require_lighting === true}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      require_lighting: event.target.checked ? true : null,
                    })
                  }
                />
                Unikaj nieoświetlonych odcinków
              </label>
              <Numeric
                label="Maksymalna wysokość krawężnika (cm)"
                value={draft.max_kerb_height_cm ?? null}
                onChange={(value) =>
                  setDraft({ ...draft, max_kerb_height_cm: value })
                }
              />
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={
                    draft.allowed_smoothness !== null &&
                    draft.allowed_smoothness !== undefined
                  }
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      allowed_smoothness: event.target.checked
                        ? ["excellent", "good"]
                        : null,
                    })
                  }
                />
                Unikaj nierównej nawierzchni
              </label>
              <div className="actions">
                <button
                  type="button"
                  className="button subtle"
                  disabled={saving}
                  onClick={() => setStep(1)}
                >
                  Wstecz
                </button>
                <button className="button primary" disabled={saving}>
                  {saving ? "Zapisywanie…" : "Zapisz profil"}
                </button>
              </div>
            </fieldset>
          </form>
        ) : (
          <div className="success-state">
            <span className="success-icon">
              <Check size={36} />
            </span>
            <h2 tabIndex={-1}>Twoje potrzeby są zapisane</h2>
            <p>
              {session
                ? "Profil zapisano na Twoim koncie. Będzie dostępny po ponownym zalogowaniu."
                : "Ustawienia zastosowano w bieżącej karcie. Zaloguj się, aby zapisać profil na koncie."}
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
