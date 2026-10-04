import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Settings2,
  ArrowRight,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import { useDemo } from "../state/DemoContext";
import MapView from "../components/MapView";
import Numeric from "../components/Numeric";
import AISearch from "../components/AISearch";
import ProfileSettingsButton from "../components/ProfileSettingsButton";
import { SearchBox, PlaceCard } from "../components/Common";
import { searchPlaces } from "../data/api";
import { places as examplePlaces } from "../data/mock";
import type { PlaceSummary } from "../data/types";
import { emptyConstraints } from "../data/types";
const filterOptions = [
  { label: "Bez schodów", key: "require_step_free_access" },
  { label: "Toaleta dostępna", key: "require_accessible_toilet" },
] as const;
const krakowCenter = { lat: 50.061, lon: 19.936 };
export function SearchPage({ mapOnly = false }: { mapOnly?: boolean }) {
  const [params, setParams] = useSearchParams();
  const { constraints, setConstraints, location } = useDemo();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [view, setView] = useState(mapOnly ? "map" : "list");
  const [sort, setSort] = useState("match");
  const [searchNear, setSearchNear] = useState(krakowCenter);
  const query = params.get("q") || "";
  const category = params.get("category") || "";
  const [results, setResults] = useState<PlaceSummary[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [selectedPlace, setSelectedPlace] = useState<PlaceSummary | null>(null);
  const isDefaultBrowse =
    !query &&
    !category &&
    Object.values(constraints).every((value) => value === null) &&
    searchNear.lat === krakowCenter.lat &&
    searchNear.lon === krakowCenter.lon;
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setSelectedPlace(null);
    setLoading(true);
    setError("");
    setResults([]);
    setTotalCount(0);
    setCurrentPage(1);
    setNextCursor(null);
    searchPlaces(
      query || category,
      constraints,
      null,
      searchNear,
      10,
      controller.signal,
    )
      .then((page) => {
        if (active) {
          const isSample = !page.items.length && isDefaultBrowse;
          const items = isSample
            ? examplePlaces.slice(0, 4).map((place) => ({
                ...place,
                is_example: true,
              }))
            : page.items;
          setResults(items);
          setNextCursor(page.next_cursor);
          setTotalCount(isSample ? items.length : page.total_count ?? items.length);
        }
      })
      .catch((reason: unknown) => {
        if (active)
          setError(
            reason instanceof Error
              ? reason.message
              : "Nie udało się pobrać miejsc.",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [query, category, constraints, searchNear, isDefaultBrowse]);
  async function goToPage(pageNumber: number) {
    if (pageNumber < 1 || pageNumber > Math.ceil(totalCount / 10)) return;
    if (pageNumber * 10 > results.length && nextCursor && !loadingMore) {
      setLoadingMore(true);
      setError("");
      try {
        let cursor: string | null = nextCursor;
        let loaded = results;
        while (loaded.length < pageNumber * 10 && cursor) {
          const page = await searchPlaces(
            query || category,
            constraints,
            cursor,
            searchNear,
            10,
          );
          loaded = [...loaded, ...page.items];
          cursor = page.next_cursor;
        }
        setResults(loaded);
        setNextCursor(cursor);
      } catch (reason: unknown) {
        setError(
          reason instanceof Error
            ? reason.message
            : "Nie udało się pobrać kolejnych miejsc.",
        );
        return;
      } finally {
        setLoadingMore(false);
      }
    }
    setCurrentPage(pageNumber);
  }
  const totalPages = Math.ceil(totalCount / 10);
  const pageWindowStart = Math.floor((currentPage - 1) / 5) * 5 + 1;
  const visiblePages = Array.from(
    { length: Math.min(5, totalPages - pageWindowStart + 1) },
    (_, index) => pageWindowStart + index,
  );
  const orderedResults = [...results].sort((a, b) =>
    sort === "distance"
      ? (a.distance_m ?? Infinity) - (b.distance_m ?? Infinity)
      : sort === "name"
        ? a.name.localeCompare(b.name, "pl")
        : Number(b.assessment?.status === "meets_requirements") -
          Number(a.assessment?.status === "meets_requirements"),
  );
  return (
    <div className={`search-page ${mapOnly ? "map-page" : ""}`}>
      <div className="search-top">
        <div>
          <p className="eyebrow">ODKRYWAJ PO SWOJEMU</p>
          <h1>{mapOnly ? "Mapa Krakowa" : "Znajdź swoje miejsce"}</h1>
        </div>
        <Link className="button subtle" to="/places/new">
          Dodaj nowe miejsce
        </Link>
      </div>
      <div className="search-controls">
        <SearchBox key={query} initial={query} />
        <label className="field search-sort">
          Sortuj według
          <select
            value={sort}
            onChange={(e) => {
              const nextSort = e.target.value;
              setSort(nextSort);
              setSearchNear(nextSort === "distance" ? location! : krakowCenter);
              setCurrentPage(1);
              setSelectedPlace(null);
            }}
          >
            <option value="match">Najlepsze dopasowanie</option>
            <option value="distance" disabled={!location}>
              Odległość
            </option>
            <option value="name">Nazwa miejsca</option>
          </select>
        </label>
      </div>
      <div className="profile-settings-control">
        <ProfileSettingsButton />
      </div>
      <AISearch
        mode="places"
        onApply={(proposal) => {
          setParams({ q: proposal.query || "*" });
        }}
      />
      <div className="mobile-search">
        <div className="toolbar">
          <button
            className="button subtle"
            onClick={() => setFiltersOpen(!filtersOpen)}
            aria-expanded={filtersOpen}
            aria-controls="search-filters"
          >
            <Settings2 size={18} />
            Filtry
          </button>
          <div className="segmented">
            <button
              className={view === "list" ? "active" : ""}
              aria-pressed={view === "list"}
              onClick={() => setView("list")}
            >
              Lista
            </button>
            <button
              className={view === "map" ? "active" : ""}
              aria-pressed={view === "map"}
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
          id="search-filters"
          aria-label="Filtry wyszukiwania"
        >
          <h2>Dopasuj do swoich potrzeb</h2>
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
          </div>
          <hr />
          <button
            className="text-button"
            onClick={() => {
              setConstraints({ ...emptyConstraints });
              setParams({});
            }}
          >
            Wyczyść filtry
          </button>
        </aside>
        <section
          className={`results ${view === "map" ? "mobile-hidden" : ""}`}
          aria-label="Lista miejsc"
        >
          <div className="results-heading">
            <h2>{category || query || "Miejsca w Krakowie"}</h2>
            <span aria-live="polite">
              {loading
                ? "Pobieranie…"
                : `${totalCount} ${totalCount === 1 ? "wynik" : totalCount % 10 >= 2 && totalCount % 10 <= 4 && (totalCount % 100 < 12 || totalCount % 100 > 14) ? "wyniki" : "wyników"}`}
            </span>
          </div>
          {error && (
            <p className="warning-box" role="alert">
              {error}
            </p>
          )}
          {results.length ? (
            <>
              {orderedResults
                .slice((currentPage - 1) * 10, currentPage * 10)
                .map((p) => (
                  <PlaceCard
                    key={p.id}
                    place={p}
                    onShowOnMap={() => {
                      setSelectedPlace(p);
                      setView("map");
                      requestAnimationFrame(() =>
                        document
                          .querySelector<HTMLElement>(".search-map .map-canvas")
                          ?.focus(),
                      );
                    }}
                  />
                ))}
              {totalPages > 1 && (
                <nav className="results-pagination" aria-label="Strony wyników">
                  <button
                    className="button subtle"
                    aria-label="Pierwsza strona"
                    title="Pierwsza strona"
                    onClick={() => goToPage(1)}
                    disabled={loadingMore || currentPage === 1}
                  >
                    <ChevronsLeft size={18} />
                  </button>
                  <button
                    className="button subtle"
                    aria-label="Poprzednie 5 stron"
                    title="Poprzednie 5 stron"
                    onClick={() => goToPage(Math.max(1, pageWindowStart - 5))}
                    disabled={loadingMore || pageWindowStart === 1}
                  >
                    <ChevronLeft size={18} />
                  </button>
                  {visiblePages.map((page) => (
                    <button
                      key={page}
                      className={`button subtle ${page === currentPage ? "active" : ""}`}
                      onClick={() => goToPage(page)}
                      disabled={loadingMore}
                      aria-current={page === currentPage ? "page" : undefined}
                    >
                      {page}
                    </button>
                  ))}
                  <button
                    className="button subtle"
                    aria-label="Następne 5 stron"
                    title="Następne 5 stron"
                    onClick={() =>
                      goToPage(Math.min(totalPages, pageWindowStart + 5))
                    }
                    disabled={loadingMore || pageWindowStart + 5 > totalPages}
                  >
                    <ChevronRight size={18} />
                  </button>
                  <button
                    className="button subtle"
                    aria-label="Ostatnia strona"
                    title="Ostatnia strona"
                    onClick={() => goToPage(totalPages)}
                    disabled={loadingMore || currentPage === totalPages}
                  >
                    <ChevronsRight size={18} />
                  </button>
                </nav>
              )}
            </>
          ) : !error && !loading ? (
            <div className="empty-state">
              <Search size={36} />
              <h2>Nie znaleźliśmy miejsc</h2>
              <p>Zmień frazę lub usuń część filtrów.</p>
              <button
                className="button subtle"
                onClick={() => {
                  setConstraints({ ...emptyConstraints });
                  setParams({});
                }}
              >
                Pokaż wszystkie miejsca
              </button>
            </div>
          ) : null}
        </section>
        <section
          className={`search-map ${view === "list" ? "mobile-hidden" : ""}`}
          aria-label="Mapa wyników"
        >
          {selectedPlace && (
            <button
              className="button subtle"
              onClick={() => setSelectedPlace(null)}
            >
              Pokaż wszystkie wyniki na mapie
            </button>
          )}
          <MapView
            selectedPlaceId={selectedPlace?.id}
            places={
              selectedPlace
                ? [selectedPlace]
                : orderedResults.slice((currentPage - 1) * 10, currentPage * 10)
            }
            userLocation={location}
          />

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
