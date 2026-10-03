import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { UserRound, MapPin, ArrowRight } from "lucide-react";
import { useDemo } from "../state/DemoContext";
import { PageHeading } from "../components/Common";
export function Auth({ register = false }: { register?: boolean }) {
  const { setUser } = useDemo();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  return (
    <div className="page auth-page">
      <div className="panel">
        <span className="option-icon good">
          <UserRound />
        </span>
        <PageHeading
          title={
            register ? "Utwórz konto demonstracyjne" : "Wejdź na konto demo"
          }
          description="To lokalna symulacja konta. Nie podawaj prawdziwego hasła ani danych logowania."
        />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setUser(name.trim());
            navigate("/profile");
          }}
        >
          <label className="field">
            Nazwa w demonstracji
            <input
              required
              maxLength={100}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Np. Anna"
              autoComplete="off"
            />
          </label>
          <button className="button primary full">
            {register ? "Utwórz konto demo" : "Kontynuuj"}
          </button>
        </form>
        <Link className="text-button" to="/search">
          Korzystaj bez konta
        </Link>
      </div>
    </div>
  );
}
export function About() {
  return (
    <div className="page narrow">
      <PageHeading
        eyebrow="KRAKÓW BEZ BARIER"
        title="Każdy ma swoją drogę"
        description="Swoją Drogą pomaga sprawdzić konkretne cechy miejsc i zaplanować spacer dopasowany do własnych potrzeb."
      />
      <div className="panel prose">
        <h2>Informacje, które dają wybór</h2>
        <p>
          Pokazujemy stopnie, progi, szerokość wejść, toalety, podjazdy i
          miejsca odpoczynku. Każda informacja ma źródło, datę oraz ocenę
          wiarygodności.
        </p>
        <h2>Co wiemy, a czego jeszcze nie?</h2>
        <p>
          Brakujące, sprzeczne i stare dane oznaczamy jako niepotwierdzone.
          Procent wiarygodności nie zastępuje potwierdzenia. Dopasowanie zależy
          od wskazanych przez Ciebie potrzeb.
        </p>
        <h2>O tej demonstracji</h2>
        <p>
          Wszystkie dane są przykładowe. Ilustracje i schemat mapy nie
          odzwierciedlają rzeczywistych warunków. Trasa jest stałym scenariuszem
          prezentacyjnym, a nawigacja nie śledzi pozycji.
        </p>
        <p>
          Profil, zapisane miejsca, konto demo, zgłoszenia i postępy misji
          pozostają w pamięci bieżącej karty. Odświeżenie strony je usuwa. Nie
          wysyłamy opisu potrzeb ani zdjęć do serwera.
        </p>
        <h2>Dostępność</h2>
        <p>
          Interfejs ma tekstowy odpowiednik mapy, etykiety formularzy, widoczny
          fokus i obsługę klawiaturą. Pełna zgodność z WCAG 2.2 AA wymaga
          osobnego badania, w tym czytnikiem ekranu.
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
      <p>Wróć do wyszukiwania i wybierz przykładowe miejsce.</p>
      <Link className="button primary" to="/search">
        Szukaj miejsc
      </Link>
    </div>
  );
}
