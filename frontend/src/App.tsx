import { useState, useEffect, useRef, type ReactNode } from "react";
import {
  Link,
  NavLink,
  Navigate,
  Routes,
  Route,
  useLocation,
} from "react-router-dom";
import {
  Search,
  Route as RouteIcon,
  Flag,
  Star,
  UserRound,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { translate, textLanguage, useLanguage, setLanguage } from "./i18n";
import { Context, useDemo, type DemoState } from "./state/DemoContext";
import { emptyConstraints, type Constraints, type Report } from "./data/types";
import {
  api,
  ApiError,
  listAll,
  login,
  register,
  logout,
  restoreSession,
  saveNeedsProfile,
  getMissionActivity,
  type Session,
  type Profile as NeedsProfile,
  type MissionActivity,
} from "./data/api";
import { Home } from "./pages/Home";
import { SearchPage } from "./pages/Search";
import { PlacePage } from "./pages/Place";
import { NeedsPage } from "./pages/Needs";
import { RoutePage, RouteDetails, Navigation } from "./pages/Routes";
import {
  ReportHub,
  ReportForm,
  ReportSuccess,
  VerificationRequestForm,
} from "./pages/Reports";
import { MissionsPage, MissionPage } from "./pages/Missions";
import { NearbyMissions } from "./components/NearbyMissions";
import { Profile } from "./pages/Profile";
import { ReviewPage } from "./pages/Review";
import { Auth, About, NotFound } from "./pages/Info";
import { PublicData, Privacy, DataQuality } from "./pages/DataPolicies";
const nav = [
  { to: "/search", label: "Miejsca", icon: Search },
  { to: "/route", label: "Trasy", icon: RouteIcon },
  { to: "/report", label: "Zgłoś", icon: Flag },
  { to: "/missions", label: "Misje", icon: Star },
];
function Layout({
  children,
  message,
  dismissMessage,
}: {
  children: ReactNode;
  message: string;
  dismissMessage: () => void;
}) {
  const { user, signOut, notify } = useDemo();
  const [menu, setMenu] = useState(false);
  const location = useLocation();
  const language = useLanguage();
  const languageTransition = useRef(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const languageFlag =
    language === "pl" ? (
      <svg className="language-flag" viewBox="0 0 60 40" aria-hidden="true">
        <path fill="#012169" d="M0 0h60v40H0z" />
        <path stroke="#fff" strokeWidth="8" d="m0 0 60 40M60 0 0 40" />
        <path stroke="#c8102e" strokeWidth="3" d="m0 0 60 40M60 0 0 40" />
        <path stroke="#fff" strokeWidth="13" d="M30 0v40M0 20h60" />
        <path stroke="#c8102e" strokeWidth="7" d="M30 0v40M0 20h60" />
      </svg>
    ) : (
      <svg className="language-flag" viewBox="0 0 60 40" aria-hidden="true">
        <path fill="#fff" d="M0 0h60v20H0z" />
        <path fill="#dc143c" d="M0 20h60v20H0z" />
      </svg>
    );
  useEffect(() => {
    document.documentElement.lang = language;
    const root = document.getElementById("root");
    if (!root) return;
    const apply = (node: Node) => {
      if (node.nodeType === Node.TEXT_NODE && node.textContent) {
        const translated = translate(node.textContent);
        if (translated !== node.textContent) node.textContent = translated;
      } else if (node instanceof HTMLElement) {
        if (node.hasAttribute("data-no-translate")) {
          node.lang = "pl";
          return;
        }
        for (const attr of ["aria-label", "placeholder", "title", "alt"]) {
          const value = node.getAttribute(attr);
          if (value) {
            const translated = translate(value);
            if (translated !== value) node.setAttribute(attr, translated);
          }
        }
        if (!(node instanceof HTMLTextAreaElement))
          node.childNodes.forEach(apply);
        const copy = Array.from(node.childNodes)
          .filter((child) => child.nodeType === Node.TEXT_NODE)
          .map((child) => child.textContent || "");
        for (const attr of ["aria-label", "title", "alt"]) {
          const value = node.getAttribute(attr);
          if (value) copy.push(value);
        }
        node.lang = textLanguage(copy);
      }
    };
    root.childNodes.forEach(apply);
    const observer = new MutationObserver((records) =>
      records.forEach((record) => {
        if (record.type === "childList") apply(record.target);
        if (record.type === "characterData" && record.target.parentElement)
          apply(record.target.parentElement);
        if (
          record.type === "attributes" &&
          record.target instanceof HTMLElement
        ) {
          const attr = record.attributeName;
          const value = attr && record.target.getAttribute(attr);
          if (attr && value) {
            const translated = translate(value);
            if (translated !== value)
              record.target.setAttribute(attr, translated);
          }
        }
      }),
    );
    observer.observe(root, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["aria-label", "placeholder", "title", "alt"],
    });
    return () => observer.disconnect();
  }, [language]);
  useEffect(() => {
    if (!languageTransition.current) return;
    const frame = requestAnimationFrame(() => {
      document.getElementById("root")?.classList.remove("language-changing");
      languageTransition.current = false;
    });
    return () => cancelAnimationFrame(frame);
  }, [language]);
  const changeLanguage = () => {
    if (languageTransition.current) return;
    const root = document.getElementById("root");
    if (!root) {
      setLanguage(language === "pl" ? "en" : "pl");
      return;
    }
    languageTransition.current = true;
    root.classList.add("language-changing");
    window.setTimeout(() => setLanguage(language === "pl" ? "en" : "pl"), 140);
  };
  useEffect(() => {
    setMenu(false);
    window.scrollTo(0, 0);
    document.getElementById("content")?.focus({ preventScroll: true });
  }, [location.pathname]);
  useEffect(() => {
    const content = document.getElementById("content");
    if (!content) return;
    const update = () => {
      const heading = content.querySelector("h1");
      const title = heading?.innerText?.replace(/\s+/g, " ").trim();
      document.title = title ? `${title} · Swoją Drogą` : "Swoją Drogą";
      if (heading) {
        heading.tabIndex = -1;
        if (document.activeElement === content)
          heading.focus({ preventScroll: true });
      }
    };
    update();
    const observer = new MutationObserver(update);
    observer.observe(content, {
      childList: true,
      characterData: true,
      subtree: true,
    });
    return () => observer.disconnect();
  }, [location.pathname, language]);
  useEffect(() => {
    if (!menu) return;
    document.querySelector<HTMLElement>("#main-navigation a")?.focus();
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenu(false);
        menuButton.current?.focus();
      }
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [menu]);
  useEffect(() => {
    const header = document.querySelector<HTMLElement>(".header");
    const bottom = document.querySelector<HTMLElement>(".bottom-nav");
    const update = () => {
      document.documentElement.style.setProperty(
        "--focus-top",
        `${header?.getBoundingClientRect().height || 0}px`,
      );
      document.documentElement.style.setProperty(
        "--focus-bottom",
        `${bottom?.getBoundingClientRect().height || 0}px`,
      );
    };
    const observer = new ResizeObserver(update);
    if (header) observer.observe(header);
    if (bottom) observer.observe(bottom);
    update();
    return () => observer.disconnect();
  }, [location.pathname]);
  const navigating = location.pathname === "/navigation";
  return (
    <>
      <a
        href="#content"
        className="skip-link"
        onClick={() => document.getElementById("content")?.focus()}
      >
        Przejdź do treści
      </a>
      <header
        className="header"
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null))
            setMenu(false);
        }}
      >
        <Link to="/" className="brand">
          <span className="brand-icon">
            <img src="/logo.png" alt="" />
          </span>
          <span>
            <strong>Swoją Drogą</strong>
            <small>Kraków bez barier</small>
          </span>
        </Link>
        <nav
          id="main-navigation"
          className={`desktop-nav ${menu ? "open" : ""}`}
          aria-label="Nawigacja główna"
        >
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to}>
              {n.label}
            </NavLink>
          ))}
          <NavLink to="/about">O projekcie</NavLink>
          <div className="mobile-account-links">
            {user ? (
              <NavLink to="/profile">Twój profil</NavLink>
            ) : (
              <>
                <NavLink to="/login">Zaloguj się</NavLink>
                <NavLink to="/register">Utwórz konto</NavLink>
              </>
            )}
          </div>
        </nav>
        <div className="account-nav">
          <button
            className="icon-button language-switch"
            onClick={changeLanguage}
            aria-label={
              language === "pl" ? "Switch to English" : "Przełącz na polski"
            }
            title={language === "pl" ? "English" : "Polski"}
          >
            {languageFlag}
          </button>
          {user ? (
            <>
              <Link className="button subtle" to="/profile">
                <UserRound size={19} />
                {user}
              </Link>
              <button
                className="icon-button"
                onClick={() =>
                  void signOut().catch((error: unknown) => {
                    notify(
                      error instanceof Error
                        ? error.message
                        : "Nie udało się wylogować.",
                    );
                  })
                }
                aria-label="Wyloguj się"
                title="Wyloguj się"
              >
                <LogOut size={19} />
              </button>
            </>
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
          ref={menuButton}
          className="mobile-menu icon-button"
          onClick={() => setMenu(!menu)}
          aria-label="Menu"
          aria-expanded={menu}
          aria-controls="main-navigation"
        >
          {menu ? <X /> : <Menu />}
        </button>
      </header>
      <main id="content" tabIndex={-1}>
        <div
          className="toast-region"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          {message && (
            <div className="toast">
              <span>{message}</span>
              <button
                aria-label="Zamknij komunikat"
                onClick={() => {
                  dismissMessage();
                  document
                    .getElementById("content")
                    ?.focus({ preventScroll: true });
                }}
              >
                <X size={18} />
              </button>
            </div>
          )}
        </div>
        <NearbyMissions />
        {children}
      </main>
      {!navigating && (
        <>
          <footer>
            <Link className="footer-brand" to="/">
              Swoją Drogą
            </Link>
            <span>Więcej możliwości. Mniej barier.</span>
            <nav className="footer-links" aria-label="Informacje o projekcie">
              <Link to="/about">O projekcie</Link>
              <Link to="/public-data">Dane publiczne</Link>
              <Link to="/privacy">Prywatność i bezpieczeństwo</Link>
              <Link to="/data-quality">Źródła i aktualność</Link>
            </nav>
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
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<NeedsProfile | null>(null);
  const [activity, setActivity] = useState<MissionActivity>({
    items: [],
    points: 0,
  });
  const [ready, setReady] = useState(false);
  const [location, setLocation] = useState<{ lat: number; lon: number } | null>(
    null,
  );
  const accountVersion = useRef(0);
  const activeSession = useRef<Session | null>(null);
  const [message, notify] = useState("");
  useEffect(() => {
    if (!navigator.geolocation) return;
    const watchId = navigator.geolocation.watchPosition(
      ({ coords }) =>
        setLocation({ lat: coords.latitude, lon: coords.longitude }),
      () => setLocation(null),
      { enableHighAccuracy: false, maximumAge: 60_000, timeout: 10_000 },
    );
    return () => navigator.geolocation.clearWatch(watchId);
  }, []);
  async function loadAccount(next: Session | null) {
    const version = ++accountVersion.current;
    activeSession.current = next;
    setSession(next);
    setProfile(null);
    setReports([]);
    setSaved([]);
    setActivity({ items: [], points: 0 });
    setConstraints({ ...emptyConstraints });
    if (!next) return;
    const results = await Promise.allSettled([
      listAll<NeedsProfile>("/profiles"),
      listAll<Report>("/reports?mine=true"),
      api<string[]>("/bookmarks"),
      getMissionActivity(),
    ]);
    if (version !== accountVersion.current) return;
    const [profilesResult, reportsResult, savedResult, activityResult] =
      results;
    if (profilesResult.status === "fulfilled") {
      const current =
        profilesResult.value.find(
          (item) => item.name === "Mój profil potrzeb",
        ) || profilesResult.value[0];
      setProfile(current || null);
      if (current) setConstraints(current.constraints);
    }
    if (reportsResult.status === "fulfilled") setReports(reportsResult.value);
    if (savedResult.status === "fulfilled") setSaved(savedResult.value);
    if (activityResult.status === "fulfilled")
      setActivity(activityResult.value);
    const failure = results.find((result) => result.status === "rejected");
    if (failure?.status === "rejected")
      notify(
        failure.reason instanceof Error
          ? failure.reason.message
          : "Nie udało się pobrać danych konta.",
      );
  }
  useEffect(() => {
    let cancelled = false;
    restoreSession()
      .then(async (next) => {
        if (!cancelled) await loadAccount(next);
      })
      .catch((error: unknown) => {
        if (!cancelled)
          notify(
            error instanceof Error
              ? error.message
              : "Nie udało się odtworzyć sesji.",
          );
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  async function refreshActivity() {
    if (!session) return;
    const version = accountVersion.current;
    const [nextReports, nextActivity] = await Promise.all([
      listAll<Report>("/reports?mine=true"),
      getMissionActivity(),
    ]);
    if (version === accountVersion.current) {
      setReports(nextReports);
      setActivity(nextActivity);
    }
  }
  const value: DemoState = {
    location,
    constraints,
    setConstraints,
    saved,
    toggleSave: async (id) => {
      const version = accountVersion.current;
      const next = saved.includes(id)
        ? saved.filter((item) => item !== id)
        : [...saved, id];
      try {
        if (session) {
          const updated = await api<string[]>("/bookmarks", {
            method: "PUT",
            body: JSON.stringify(next),
          });
          if (version === accountVersion.current) setSaved(updated);
        } else setSaved(next);
      } catch (error) {
        notify(
          error instanceof Error
            ? error.message
            : "Nie udało się zapisać miejsca.",
        );
      }
    },
    reports,
    addReport: (r) => {
      if (r.author_id === activeSession.current?.user.id)
        setReports((s) => [r, ...s]);
    },
    user: session?.user.display_name || null,
    session,
    profile,
    authenticate: async (email, password, name) => {
      if (name !== undefined) await register(email, password, name);
      await loadAccount(await login(email, password));
    },
    signOut: async () => {
      try {
        await logout();
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 401)) throw error;
      }
      await loadAccount(null);
    },
    saveProfile: async (description, nextConstraints) => {
      if (!session) {
        setConstraints(nextConstraints);
        return;
      }
      const version = accountVersion.current;
      const profiles = await listAll<NeedsProfile>("/profiles");
      if (version !== accountVersion.current)
        throw new Error("Sesja zmieniła się. Zapisz profil ponownie.");
      const current =
        profiles.find((item) => item.name === "Mój profil potrzeb") ||
        profiles[0];
      const updated = await saveNeedsProfile(
        current?.id,
        description,
        nextConstraints,
      );
      if (version !== accountVersion.current) return;
      setProfile(updated);
      setConstraints(updated.constraints);
    },
    activity,
    refreshActivity,
    notify,
  };
  return (
    <Context.Provider value={value}>
      <Layout message={message} dismissMessage={() => notify("")}>
        {!ready ? (
          <div className="page" role="status">
            Odtwarzanie sesji…
          </div>
        ) : (
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/search" element={<SearchPage key="search" />} />
            <Route path="/map" element={<Navigate to="/route" replace />} />
            <Route path="/place/:id" element={<PlacePage />} />
            <Route path="/profile/setup" element={<NeedsPage />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/review" element={<ReviewPage />} />
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
            <Route
              path="/report/verify"
              element={<VerificationRequestForm />}
            />
            <Route path="/report/success" element={<ReportSuccess />} />
            <Route path="/missions" element={<MissionsPage />} />
            <Route path="/missions/:id" element={<MissionPage />} />
            <Route path="/login" element={<Auth />} />
            <Route path="/register" element={<Auth register />} />
            <Route path="/about" element={<About />} />
            <Route path="/public-data" element={<PublicData />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/data-quality" element={<DataQuality />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        )}
      </Layout>
    </Context.Provider>
  );
}
