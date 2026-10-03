import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Settings2,
  ShieldCheck,
  ArrowRight,
  Route as RouteIcon,
  Search,
} from "lucide-react";
import { useDemo } from "../state/DemoContext";
import MapView from "../components/MapView";
import Numeric from "../components/Numeric";
import { SearchBox, PlaceCard } from "../components/Common";
import { assess, places } from "../data/mock";
import { emptyConstraints } from "../data/types";
const filterOptions = [
  { label: "Bez schodów", key: "require_step_free_access" },
  { label: "Toaleta dostępna", key: "require_accessible_toilet" },
] as const;
export function SearchPage({ mapOnly = false }: { mapOnly?: boolean }) {
  const [params, setParams] = useSearchParams();
  const { constraints, setConstraints, saved, toggleSave } = useDemo();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [view, setView] = useState(mapOnly ? "map" : "list");
  const [sort, setSort] = useState("match");
  const [seats, setSeats] = useState(false);
  const [ramp, setRamp] = useState(false);
  const [elevator, setElevator] = useState(false);
  const [sourceTypes, setSourceTypes] = useState<string[]>([]);
  const query = params.get("q") || "";
  const category = params.get("category") || "";
  const normalized = (text: string) =>
    text
      .toLocaleLowerCase("pl")
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "");
  const term = normalized(query);
  const results = places
    .filter(
      (p) =>
        (!term ||
          normalized(
            `${p.name} ${p.category} ${p.address} ${p.demo.description}`,
          ).includes(term) ||
          (term === "kawiarnia" && p.demo.image === "cafe")) &&
        (!category || p.category === category) &&
        (!seats ||
          p.facts.some(
            (f) =>
              f.attribute === "rest_area_available" &&
              f.status === "confirmed" &&
              f.value === true,
          )) &&
        (!ramp ||
          p.facts.some(
            (f) =>
              f.attribute === "ramp_available" &&
              f.status === "confirmed" &&
              f.value === true,
          )) &&
        (!elevator ||
          p.facts.some(
            (f) =>
              f.attribute === "elevator_available" &&
              f.status === "confirmed" &&
              f.value === true,
          )) &&
        (!sourceTypes.length ||
          p.facts.some((f) =>
            f.sources.some((s) => sourceTypes.includes(s.type)),
          )) &&
        assess(p, constraints).status !== "does_not_meet_requirements",
    )
    .sort((a, b) =>
      sort === "distance"
        ? a.distance_m - b.distance_m
        : sort === "name"
          ? a.name.localeCompare(b.name, "pl")
          : Number(assess(b, constraints).status === "meets_requirements") -
            Number(assess(a, constraints).status === "meets_requirements"),
    );
  return (
    <div className={`search-page ${mapOnly ? "map-page" : ""}`}>
      <div className="search-top">
        <div>
          <p className="eyebrow">ODKRYWAJ PO SWOJEMU</p>
          <h1>{mapOnly ? "Mapa Krakowa" : "Znajdź swoje miejsce"}</h1>
        </div>
        <Link className="button subtle" to="/route">
          <RouteIcon size={20} />
          Wyznacz trasę
        </Link>
      </div>
      <div className="mobile-search">
        <SearchBox key={query} initial={query} />
        <div className="toolbar">
          <button
            className="button subtle"
            onClick={() => setFiltersOpen(!filtersOpen)}
            aria-expanded={filtersOpen}
          >
            <Settings2 size={18} />
            Filtry
          </button>
          <div className="segmented">
            <button
              className={view === "list" ? "active" : ""}
              onClick={() => setView("list")}
            >
              Lista
            </button>
            <button
              className={view === "map" ? "active" : ""}
              onClick={() => setView("map")}
            >
              Mapa
            </button>
          </div>
        </div>
      </div>
      <div className="search-columns">
        <aside
          className={`filters ${filtersOpen ? "show" : ""}`}
          aria-label="Filtry wyszukiwania"
        >
          <SearchBox key={query} initial={query} compact />
          <h3>Dopasuj do swoich potrzeb</h3>
          {filterOptions.map((o) => (
            <label className="check-field" key={o.key}>
              <input
                type="checkbox"
                checked={constraints[o.key] === true}
                onChange={(e) =>
                  setConstraints({
                    ...constraints,
                    [o.key]: e.target.checked ? true : null,
                    ...(o.key === "require_step_free_access"
                      ? { max_steps: e.target.checked ? 0 : null }
                      : {}),
                  })
                }
              />
              {o.label}
            </label>
          ))}
          <label className="check-field">
            <input
              type="checkbox"
              checked={ramp}
              onChange={(e) => setRamp(e.target.checked)}
            />
            Podjazd
          </label>
          <label className="check-field">
            <input
              type="checkbox"
              checked={elevator}
              onChange={(e) => setElevator(e.target.checked)}
            />
            Winda
          </label>
          <label className="check-field">
            <input
              type="checkbox"
              checked={seats}
              onChange={(e) => setSeats(e.target.checked)}
            />
            Miejsca do siedzenia
          </label>
          <label className="check-field">
            <input
              type="checkbox"
              checked={constraints.min_entrance_width_cm === 90}
              onChange={(e) =>
                setConstraints({
                  ...constraints,
                  min_entrance_width_cm: e.target.checked ? 90 : null,
                })
              }
            />
            Szerokie wejście (min. 90 cm)
          </label>
          <label className="check-field">
            <input
              type="checkbox"
              checked={constraints.allowed_surfaces !== null}
              onChange={(e) =>
                setConstraints({
                  ...constraints,
                  allowed_surfaces: e.target.checked
                    ? ["paved", "asphalt"]
                    : null,
                })
              }
            />
            Utwardzona nawierzchnia
          </label>
          <button
            className="text-button filter-more"
            onClick={() => setAdvanced(!advanced)}
            aria-expanded={advanced}
          >
            <Settings2 size={16} />
            {advanced ? "Mniej filtrów" : "Więcej filtrów"}
          </button>
          {advanced && (
            <div className="advanced-filters">
              <Numeric
                label="Maks. liczba stopni"
                value={constraints.max_steps}
                onChange={(v) =>
                  setConstraints({
                    ...constraints,
                    max_steps: v,
                    require_step_free_access:
                      v !== null && v > 0
                        ? null
                        : constraints.require_step_free_access,
                  })
                }
              />
              <Numeric
                label="Maks. nachylenie (%)"
                value={constraints.max_slope_percent}
                onChange={(v) =>
                  setConstraints({ ...constraints, max_slope_percent: v })
                }
              />
              <Numeric
                label="Odpoczynek co (m)"
                min={1}
                value={constraints.max_distance_without_rest_m}
                onChange={(v) =>
                  setConstraints({
                    ...constraints,
                    max_distance_without_rest_m: v,
                  })
                }
              />
            </div>
          )}
          <hr />
          <h3>Źródła informacji</h3>
          {[
            { type: "owner", label: "Właściciele obiektów" },
            { type: "user", label: "Użytkownicy" },
            { type: "osm", label: "OpenStreetMap" },
          ].map((s) => (
            <label className="check-field" key={s.type}>
              <input
                type="checkbox"
                checked={sourceTypes.includes(s.type)}
                onChange={(e) =>
                  setSourceTypes(
                    e.target.checked
                      ? [...sourceTypes, s.type]
                      : sourceTypes.filter((t) => t !== s.type),
                  )
                }
              />
              {s.label}
            </label>
          ))}
          <hr />
          <label className="field">
            Sortuj według
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="match">Najlepsze dopasowanie</option>
              <option value="distance">
                Najbliżej punktu demonstracyjnego
              </option>
              <option value="name">Nazwa miejsca</option>
            </select>
          </label>
          <button
            className="text-button"
            onClick={() => {
              setConstraints({ ...emptyConstraints });
              setSeats(false);
              setRamp(false);
              setElevator(false);
              setSourceTypes([]);
              setParams({});
            }}
          >
            Wyczyść filtry
          </button>
          <div className="filter-note">
            <ShieldCheck size={21} />
            <p>
              Brak danych to ważna informacja. Zawsze pokazujemy, co wymaga
              potwierdzenia.
            </p>
          </div>
        </aside>
        <section
          className={`results ${view === "map" ? "mobile-hidden" : ""}`}
          aria-label="Lista miejsc"
        >
          <div className="results-heading">
            <h2>{category || query || "Miejsca w Krakowie"}</h2>
            <span aria-live="polite">{results.length} wyników</span>
          </div>
          {results.length ? (
            results.map((p) => (
              <PlaceCard
                key={p.id}
                place={p}
                assessment={assess(p, constraints)}
                saved={saved.includes(p.id)}
                toggle={() => toggleSave(p.id)}
              />
            ))
          ) : (
            <div className="empty-state">
              <Search size={36} />
              <h2>Nie znaleźliśmy miejsc</h2>
              <p>Zmień frazę lub usuń część filtrów.</p>
              <button
                className="button subtle"
                onClick={() => {
                  setConstraints({ ...emptyConstraints });
                  setRamp(false);
                  setSeats(false);
                  setElevator(false);
                  setSourceTypes([]);
                  setParams({});
                }}
              >
                Pokaż wszystkie miejsca
              </button>
            </div>
          )}
        </section>
        <section
          className={`search-map ${view === "list" ? "mobile-hidden" : ""}`}
          aria-label="Mapa wyników"
        >
          <MapView places={results} />
          <div className="map-legend">
            <span>✓ Informacje potwierdzone</span>
            <span>? Część danych niepotwierdzona</span>
          </div>
          {mapOnly && (
            <Link className="button subtle map-list-link" to="/search">
              Zobacz listę miejsc <ArrowRight size={18} />
            </Link>
          )}
        </section>
      </div>
    </div>
  );
}
