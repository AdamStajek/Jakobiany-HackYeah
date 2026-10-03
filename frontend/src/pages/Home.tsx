import { useState } from "react";
import { Link } from "react-router-dom";
import {
  UserRound,
  ArrowRight,
  Coffee,
  Landmark,
  Settings2,
} from "lucide-react";
import { SearchBox } from "../components/Common";
const categories = [
  { name: "Hotele", icon: Landmark, key: "Hotele" },
  { name: "Muzea", icon: Landmark, key: "Muzea" },
  { name: "Urzędy", icon: Landmark, key: "Urzędy" },
  { name: "Sklepy spożywcze", icon: Coffee, key: "Sklepy spożywcze" },
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
        </div>
        <img
          className="hero-art"
          src="/illustrations/krakow.svg"
          alt="Ilustracja Krakowa: Wawel, zieleń i ławka przy spacerowej alejce"
        />
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
    </div>
  );
}
