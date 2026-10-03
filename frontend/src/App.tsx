import { useState, useEffect, type ReactNode } from "react";
import { Link, NavLink, Routes, Route, useLocation } from "react-router-dom";
import {
  Leaf,
  Search,
  Map,
  Flag,
  Star,
  UserRound,
  Menu,
  X,
} from "lucide-react";
import { Context, useDemo, type DemoState } from "./state/DemoContext";
import { emptyConstraints, type Constraints, type Report } from "./data/types";
import { Home } from "./pages/Home";
import { SearchPage } from "./pages/Search";
import { PlacePage } from "./pages/Place";
import { NeedsPage } from "./pages/Needs";
import { RoutePage, RouteDetails, Navigation } from "./pages/Routes";
import { ReportHub, ReportForm, ReportSuccess } from "./pages/Reports";
import { MissionsPage, MissionPage } from "./pages/Missions";
import { Profile } from "./pages/Profile";
import { Auth, About, NotFound } from "./pages/Info";
const nav = [
  { to: "/search", label: "Szukaj", icon: Search },
  { to: "/map", label: "Mapa", icon: Map },
  { to: "/report", label: "Zgłoś", icon: Flag },
  { to: "/missions", label: "Misje", icon: Star },
];
function Layout({ children }: { children: ReactNode }) {
  const { user } = useDemo();
  const [menu, setMenu] = useState(false);
  const location = useLocation();
  useEffect(() => {
    setMenu(false);
    window.scrollTo(0, 0);
    document.getElementById("content")?.focus();
  }, [location.pathname, location.search]);
  const navigating = location.pathname === "/navigation";
  return (
    <>
      <a href="#content" className="skip-link">
        Przejdź do treści
      </a>
      <header className="header">
        <Link to="/" className="brand">
          <span className="brand-icon">
            <Leaf size={30} />
          </span>
          <span>
            <strong>Swoją Drogą</strong>
            <small>Kraków bez barier</small>
          </span>
        </Link>
        <nav
          className={`desktop-nav ${menu ? "open" : ""}`}
          aria-label="Nawigacja główna"
        >
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to}>
              {n.label}
            </NavLink>
          ))}
          <NavLink to="/about">O projekcie</NavLink>
        </nav>
        <div className="account-nav">
          {user ? (
            <Link className="button subtle" to="/profile">
              <UserRound size={19} />
              {user}
            </Link>
          ) : (
            <>
              <Link className="login-link" to="/login">
                Zaloguj się
              </Link>
              <Link className="button primary small" to="/register">
                Utwórz konto
              </Link>
            </>
          )}
        </div>
        <button
          className="mobile-menu icon-button"
          onClick={() => setMenu(!menu)}
          aria-label="Menu"
          aria-expanded={menu}
        >
          {menu ? <X /> : <Menu />}
        </button>
      </header>
      <div className="demo-banner">
        <span className="demo-dot" /> Wersja demonstracyjna{" "}
        <span className="demo-detail">
          · Przykładowe miejsca i trasy, bez połączenia z API
        </span>
      </div>
      <main id="content" tabIndex={-1}>
        {children}
      </main>
      {!navigating && (
        <>
          <footer>
            <Link className="footer-brand" to="/">
              Swoją Drogą
            </Link>
            <span>Więcej możliwości. Mniej barier.</span>
            <Link to="/about">O danych i projekcie</Link>
          </footer>
          <nav className="bottom-nav" aria-label="Nawigacja mobilna">
            {[...nav, { to: "/profile", label: "Profil", icon: UserRound }].map(
              (n) => (
                <NavLink key={n.to} to={n.to}>
                  <n.icon size={22} />
                  <span>{n.label}</span>
                </NavLink>
              ),
            )}
          </nav>
        </>
      )}
    </>
  );
}
export default function App() {
  const [constraints, setConstraints] = useState<Constraints>({
    ...emptyConstraints,
  });
  const [saved, setSaved] = useState<string[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [user, setUser] = useState<string | null>(null);
  const [progress, setProgressState] = useState<Record<string, string>>({});
  const [message, notify] = useState("");
  useEffect(() => {
    if (message) {
      const timeout = setTimeout(() => notify(""), 5500);
      return () => clearTimeout(timeout);
    }
  }, [message]);
  const value: DemoState = {
    constraints,
    setConstraints,
    saved,
    toggleSave: (id) =>
      setSaved((s) =>
        s.includes(id) ? s.filter((i) => i !== id) : [...s, id],
      ),
    reports,
    addReport: (r) => setReports((s) => [r, ...s]),
    user,
    setUser,
    progress,
    setProgress: (id, status) =>
      setProgressState((s) => ({ ...s, [id]: status })),
    notify,
  };
  return (
    <Context.Provider value={value}>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<SearchPage key="search" />} />
          <Route path="/map" element={<SearchPage key="map" mapOnly />} />
          <Route path="/place/:id" element={<PlacePage />} />
          <Route path="/profile/setup" element={<NeedsPage />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/route" element={<RoutePage />} />
          <Route path="/route/:id/details" element={<RouteDetails />} />
          <Route path="/navigation" element={<Navigation />} />
          <Route path="/report" element={<ReportHub />} />
          <Route
            path="/report/problem"
            element={<ReportForm key="problem" />}
          />
          <Route
            path="/report/confirm"
            element={<ReportForm key="confirm" confirm />}
          />
          <Route path="/report/success" element={<ReportSuccess />} />
          <Route path="/missions" element={<MissionsPage />} />
          <Route path="/missions/:id" element={<MissionPage />} />
          <Route path="/login" element={<Auth />} />
          <Route path="/register" element={<Auth register />} />
          <Route path="/about" element={<About />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
      <div className="toast-region" role="status" aria-live="polite">
        {message && (
          <div className="toast">
            {message}
            <button aria-label="Zamknij komunikat" onClick={() => notify("")}>
              <X size={18} />
            </button>
          </div>
        )}
      </div>
    </Context.Provider>
  );
}
