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
        <h2>Kraków na Twoich warunkach</h2>
        <p>
          „Swoją Drogą” pomaga znaleźć miejsce i zaplanować dotarcie do niego z
          uwzględnieniem Twoich potrzeb. Przyda się, gdy poruszasz się na wózku,
          idziesz z wózkiem dziecięcym, unikasz schodów lub potrzebujesz
          częściej odpocząć.
        </p>
        <h2>Znajdź miejsce, do którego chcesz się wybrać</h2>
        <p>
          Wyszukaj miejsce po nazwie, adresie lub kategorii i obejrzyj wyniki na
          mapie. W szczegółach sprawdzisz dostępne informacje o wejściu,
          schodach, podjazdach, toaletach i miejscach odpoczynku, a także
          godziny, kontakt czy zdjęcia, jeśli udało się je pozyskać. Źródła i
          daty pomagają ocenić, na ile aktualny jest opis.
        </p>
        <h2>Powiedz, co jest dla Ciebie ważne</h2>
        <p>
          Ustaw wymagania: na przykład brak schodów, minimalną szerokość
          przejścia, dopuszczalne nachylenie lub dostęp do toalety. Możesz też
          opisać potrzeby własnymi słowami — analiza AI zaproponuje ustawienia
          do sprawdzenia. Zapisany na koncie profil pozwala wracać do swoich
          preferencji.
        </p>
        <h2>Zaplanuj drogę</h2>
        <p>
          Wybierz początek i cel z katalogu lub na mapie; możesz też skorzystać
          z lokalizacji urządzenia. Planer obsługuje spacer, komunikację miejską
          i dojazd samochodem, w tym wariant z parkingiem dla osób z
          niepełnosprawnościami. Porównasz dostępne warianty, czas i odległość
          oraz ostrzeżenia o barierach, brakujących danych, remontach i
          pogodzie. Na mapie możesz również sprawdzić przystanki, dostępne
          pozycje pojazdów i parkingi OZN.
        </p>
        <h2>Pomóż kolejnym osobom</h2>
        <p>
          Po zalogowaniu zapiszesz ulubione miejsca, dodasz brakujące miejsce i
          zgłosisz zmianę, barierę lub udogodnienie. Możesz dołączyć pomiar,
          datę obserwacji i zdjęcie. Misje podpowiadają, jakie informacje warto
          sprawdzić w terenie; punkty otrzymujesz za zweryfikowane wykonanie.
        </p>
        <h2>Zacznij bez zakładania konta</h2>
        <p>
          Przeglądanie miejsc i planowanie tras nie wymaga logowania. W
          ustawieniach możesz zwiększyć tekst i kontrast. Dane mogą być niepełne
          lub nieaktualne: brak informacji o przeszkodzie nie oznacza, że jej
          nie ma. Planer pomaga przygotować podróż, ale nie prowadzi nawigacji
          ze śledzeniem Twojej pozycji.
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
