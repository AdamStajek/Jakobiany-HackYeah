import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { UserRound, MapPin, ArrowRight } from "lucide-react";
import { PageHeading } from "../components/Common";
import { useDemo } from "../state/DemoContext";
export function Auth({ register = false }: { register?: boolean }) {
  const { authenticate } = useDemo();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await authenticate(
        email.trim(),
        password,
        register ? name.trim() : undefined,
      );
      const target = params.get("next");
      navigate(
        target?.startsWith("/") && !target.startsWith("//")
          ? target
          : "/profile",
        { replace: true },
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Nie udało się zalogować.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page auth-page">
      <div className="panel">
        <span className="option-icon good">
          <UserRound />
        </span>
        <PageHeading
          title={register ? "Utwórz konto" : "Zaloguj się"}
          description="Zapisuj swoje potrzeby, wysyłaj zgłoszenia i zdobywaj punkty za zweryfikowane misje."
        />
        <form onSubmit={submit}>
          <fieldset disabled={busy} className="form-fields">
            {register && (
              <label className="field">
                Imię
                <input
                  required
                  maxLength={100}
                  autoComplete="given-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
            )}
            <label className="field">
              E-mail
              <input
                type="email"
                required
                autoComplete="email"
                maxLength={254}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label className="field">
              Hasło
              <input
                type="password"
                aria-label="Hasło"
                aria-describedby={register ? "password-help" : undefined}
                required
                minLength={12}
                maxLength={128}
                autoComplete={register ? "new-password" : "current-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              {register && (
                <small id="password-help">Co najmniej 12 znaków.</small>
              )}
            </label>
            {error && (
              <p className="warning-box" role="alert">
                {error}
              </p>
            )}
            <button className="button primary full" disabled={busy}>
              {busy
                ? "Proszę czekać…"
                : register
                  ? "Utwórz konto"
                  : "Zaloguj się"}
            </button>
          </fieldset>
        </form>
        <Link
          className="text-button"
          to={`${register ? "/login" : "/register"}${params.size ? `?${params.toString()}` : ""}`}
        >
          {register
            ? "Masz już konto? Zaloguj się"
            : "Nie masz konta? Zarejestruj się"}
        </Link>
        <Link className="text-button" to="/search">
          Korzystaj bez logowania
        </Link>
      </div>
    </div>
  );
}
export function About() {
  return (
    <div className="page narrow">
      <PageHeading
        eyebrow="SWOJĄ DROGĄ"
        title="Bo najkrótsza nie musi być twoja"
        description="Sprawdź dostępność miejsc i zaplanuj pieszą trasę dopasowaną do swoich potrzeb."
      />
      <div className="panel prose">
        <h2>Wybieraj na podstawie konkretów</h2>
        <p>
          Przy miejscach znajdziesz informacje o wejściach, schodach, toaletach,
          podjazdach i miejscach odpoczynku. Sprawdź ich źródło, datę oraz
          wiarygodność.
        </p>
        <h2>Współtwórz mapę</h2>
        <p>
          Zgłaszaj brakujące lub nieaktualne informacje. Możesz też wykonywać
          misje i dodawać zdjęcia; zgłoszenia i punkty zapisują się po
          zalogowaniu, a punkty przyznajemy po weryfikacji.
        </p>
        <p>
          Profil potrzeb pomoże dopasować wyniki, a analiza opisu może
          zaproponować ustawienia do sprawdzenia. Nie musisz się logować, by
          przeglądać miejsca.
        </p>
        <p>
          Dane i piesza sieć Krakowa mogą być niepełne lub nieaktualne. Trasa
          pomaga zaplanować spacer, ale nie śledzi Twojej pozycji.
        </p>
        <Link className="button primary" to="/search">
          Znajdź swoje miejsce <ArrowRight size={18} />
        </Link>
      </div>
    </div>
  );
}
export function NotFound() {
  return (
    <div className="page empty-state">
      <MapPin size={40} />
      <h1>Nie znaleziono tej strony</h1>
      <p>Wróć do wyszukiwania i wybierz miejsce.</p>
      <Link className="button primary" to="/search">
        Szukaj miejsc
      </Link>
    </div>
  );
}
