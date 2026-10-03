import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ShieldCheck,
  UserRound,
  ArrowRight,
  Coffee,
  Trees,
  Landmark,
  Settings2,
  Heart,
} from "lucide-react";
import { SearchBox } from "../components/Common";
const categories = [
  { name: "Hotele", icon: Landmark, key: "Hotele" },
  { name: "Muzea", icon: Landmark, key: "Muzea" },
  { name: "Urzędy", icon: Landmark, key: "Urzędy" },
  { name: "Sklepy spożywcze", icon: Coffee, key: "Sklepy spożywcze" },
  { name: "Ogrody", icon: Trees, key: "Ogrody" },
  { name: "Biblioteki", icon: Landmark, key: "Biblioteki" },
  { name: "Kluby seniora", icon: UserRound, key: "Kluby seniora" },
];
export function Home() {
  const [dismiss, setDismiss] = useState(false);
  return (
    <div className="home">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">
            <span className="tiny-line" /> KRAKÓW DLA KAŻDEGO
          </p>
          <h1>
            Odkrywaj Kraków
            <br />
            na swoich <em>zasadach.</em>
          </h1>
          <p className="hero-description">
            Sprawdzaj dostępność miejsc i tras
            <br className="desktop-break" /> dopasowanych do Twoich potrzeb.
          </p>
          <SearchBox />
          <div className="popular">
            <span>Popularne:</span>
            {["muzeum", "hotel", "ogród", "biblioteka"].map((q) => (
              <Link key={q} to={`/search?q=${q}`}>
                {q}
              </Link>
            ))}
          </div>
        </div>
        <img
          className="hero-art"
          src="/illustrations/krakow.svg"
          alt="Ilustracja Krakowa: Wawel, zieleń i ławka przy spacerowej alejce"
        />
        <div className="hero-note">
          <Heart size={19} />
          <span>
            Twoje tempo.
            <br />
            <strong>Twoja droga.</strong>
          </span>
        </div>
      </section>
      <section className="category-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">DOBRE MIEJSCE NA POCZĄTEK</p>
            <h2>Dokąd dziś się wybierasz?</h2>
          </div>
          <Link to="/search">
            Wszystkie miejsca <ArrowRight size={18} />
          </Link>
        </div>
        <div className="categories">
          {categories.map(({ name, icon: Icon, key }) => (
            <Link
              key={key}
              to={
                key === "trasa"
                  ? "/route"
                  : `/search?category=${encodeURIComponent(name)}`
              }
              className={`category category-${key}`}
            >
              <span>
                <Icon size={28} />
              </span>
              <strong>{name}</strong>
              <ArrowRight size={17} />
            </Link>
          ))}
        </div>
      </section>
      {!dismiss && (
        <section className="needs-banner">
          <div className="needs-icon">
            <Settings2 size={32} />
          </div>
          <div>
            <p className="eyebrow">KAŻDY MA SWOJĄ DROGĘ</p>
            <h2>Dopasuj wyniki do swoich potrzeb</h2>
            <p>
              Powiedz, co jest dla Ciebie ważne. Resztę odkrywaj w swoim tempie.
            </p>
          </div>
          <div className="needs-actions">
            <Link className="button primary" to="/profile/setup">
              Utwórz profil potrzeb <ArrowRight size={18} />
            </Link>
            <button className="text-button" onClick={() => setDismiss(true)}>
              Na razie pomiń
            </button>
          </div>
        </section>
      )}
      <section className="trust-strip">
        <div>
          <ShieldCheck />
          <span>
            <strong>Konkretne informacje</strong>
            <small>Schody, podjazdy, ławki i więcej</small>
          </span>
        </div>
        <div>
          <UserRound />
          <span>
            <strong>Bez obowiązku logowania</strong>
            <small>Po prostu znajdź swoją drogę</small>
          </span>
        </div>
        <div>
          <Heart />
          <span>
            <strong>Wspólnie bez barier</strong>
            <small>Twoje informacje pomagają innym</small>
          </span>
        </div>
      </section>
    </div>
  );
}
