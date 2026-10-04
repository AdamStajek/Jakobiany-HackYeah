import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  LocateFixed,
} from "lucide-react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { MobilityPoint, PlannedRoute, RouteGeometry } from "../data/api";
import type { PlaceSummary } from "../data/types";
import { translate, useLanguage } from "../i18n";

const noEndpoints: { lat: number; lon: number; label: string }[] = [];
const noMobility: MobilityPoint[] = [];
const noVariants: PlannedRoute[] = [];
const center: L.LatLngTuple = [50.061, 19.936];
export default function MapView({
  places,
  selectedPlaceId,
  route,
  routeVariants = noVariants,
  onSelectPoint,
  onCancelSelection,
  endpoints = noEndpoints,
  userLocation,
  mobility = noMobility,
  segments,
}: {
  places: PlaceSummary[];
  selectedPlaceId?: string | null;
  route?: RouteGeometry;
  routeVariants?: PlannedRoute[];
  onSelectPoint?: (point: { lat: number; lon: number }) => void;
  onCancelSelection?: () => void;
  endpoints?: { lat: number; lon: number; label: string }[];
  userLocation?: { lat: number; lon: number } | null;
  mobility?: MobilityPoint[];
  segments?: PlannedRoute["segments"];
}) {
  const language = useLanguage();
  const container = useRef<HTMLDivElement>(null);
  const helpId = useId();
  const popupClose = useRef<HTMLButtonElement>(null);
  const markerTrigger = useRef<HTMLElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const nativePopup = useRef<L.Popup | null>(null);
  const boundsRef = useRef<L.LatLngBounds | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [tileError, setTileError] = useState(false);
  const [mapCenter, setMapCenter] = useState({
    lat: center[0],
    lon: center[1],
  });
  const active = places.find((place) => place.id === selected);
  const variants = routeVariants.filter(
    (variant) => variant.variant === "fastest" || variant.variant === "constrained",
  );

  useEffect(() => {
    if (!container.current) return;
    const map = L.map(container.current, {
      zoomControl: false,
      zoomAnimation: false,
      fadeAnimation: false,
    }).setView(center, 14);
    mapRef.current = map;
    map.on("popupopen", (event: L.PopupEvent) => {
      nativePopup.current = event.popup;
      markerTrigger.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      const popup = event.popup.getElement();
      popup?.setAttribute("role", "region");
      popup?.setAttribute("aria-label", translate("Szczegóły punktu na mapie"));
      const close = popup?.querySelector<HTMLAnchorElement>(
        ".leaflet-popup-close-button",
      );
      close?.setAttribute(
        "aria-label",
        translate("Zamknij szczegóły znacznika"),
      );
      close?.focus();
    });
    map.on("popupclose", () => {
      nativePopup.current = null;
      if (markerTrigger.current?.isConnected) markerTrigger.current.focus();
      else container.current?.focus();
    });
    map.on("moveend", () => {
      const point = map.getCenter();
      setMapCenter({ lat: point.lat, lon: point.lng });
    });
    const updateZoom = () => {
      map.getContainer().dataset.zoom = String(map.getZoom());
    };
    map.on("zoomend", updateZoom);
    updateZoom();
    L.control
      .zoom({
        position: "bottomright",
        zoomInTitle: "Powiększ mapę",
        zoomOutTitle: "Pomniejsz mapę",
      })
      .addTo(map);
    map
      .getContainer()
      .querySelector(".leaflet-control-zoom-in")
      ?.setAttribute("aria-label", "Powiększ mapę");
    map
      .getContainer()
      .querySelector(".leaflet-control-zoom-out")
      ?.setAttribute("aria-label", "Pomniejsz mapę");
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);
    const resize = new ResizeObserver(() => map.invalidateSize());
    resize.observe(container.current);
    return () => {
      resize.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    L.tileLayer(
      language === "en"
        ? "https://cdn.lima-labs.com/{z}/{x}/{y}.png?api=demo"
        : "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        maxZoom: 19,
        maxNativeZoom: 19,
        attribution:
          language === "en"
            ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://maps.lima-labs.com/">Lima Labs</a>'
            : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
    )
      .on("tileerror", () => setTileError(true))
      .on("tileload", () => setTileError(false))
      .addTo(map);
    return () => {
      map.eachLayer((layer) => {
        if (layer instanceof L.TileLayer) map.removeLayer(layer);
      });
    };
  }, [language]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.eachLayer((layer) => {
      if (layer instanceof L.Marker) {
        const element = layer.getElement();
        const label = `${translate("Pokaż na mapie:")} ${layer.options.alt}`;
        element?.setAttribute("title", label);
        element?.setAttribute("aria-label", label);
      }
    });
  }, [language]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !onSelectPoint) return;
    const select = (event: L.LeafletMouseEvent) =>
      onSelectPoint({ lat: event.latlng.lat, lon: event.latlng.lng });
    map.on("click", select);
    return () => {
      map.off("click", select);
    };
  }, [onSelectPoint]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const layers = L.featureGroup().addTo(map);
    for (const place of places) {
      const { lat, lon } = place.location;
      if (
        !Number.isFinite(lat) ||
        !Number.isFinite(lon) ||
        Math.abs(lat) > 90 ||
        Math.abs(lon) > 180
      )
        continue;
      const icon = L.divIcon({
        className: `place-marker${
          place.id === selectedPlaceId ? " place-marker-selected" : ""
        }`,
        html: '<span class="place-marker-pin" aria-hidden="true"></span>',
        iconSize: [36, 44],
        iconAnchor: [18, 44],
      });
      const marker = L.marker([lat, lon], {
        icon,
        title: `${translate("Pokaż na mapie:")} ${place.name}`,
        alt: place.name,
      })
        .on(
          "keydown",
          (event: L.LeafletEvent & { originalEvent: KeyboardEvent }) => {
            if (
              event.originalEvent.key === "Enter" ||
              event.originalEvent.key === " "
            ) {
              L.DomEvent.stop(event.originalEvent);
              marker.fire("click");
            }
          },
        )
        .on("click", () => {
          layers.eachLayer((layer) => {
            if (layer instanceof L.Marker && layer !== marker)
              layer.getElement()?.classList.remove("place-marker-selected");
          });
          marker.getElement()?.classList.add("place-marker-selected");
          markerTrigger.current = marker.getElement() || null;
          setSelected(place.id);
        })
        .addTo(layers);
      marker
        .getElement()
        ?.setAttribute(
          "aria-label",
          `${translate("Pokaż na mapie:")} ${place.name}`,
        );
    }
    if (
      userLocation &&
      Number.isFinite(userLocation.lat) &&
      Number.isFinite(userLocation.lon)
    ) {
      L.circleMarker([userLocation.lat, userLocation.lon], {
        radius: 9,
        color: "white",
        weight: 3,
        fillColor: "#1a73e8",
        fillOpacity: 1,
      })
        .bindTooltip("Twoja lokalizacja")
        .addTo(layers);
    }
    for (const [index, point] of endpoints.entries()) {
      L.circleMarker([point.lat, point.lon], {
        radius: 9,
        color: "white",
        weight: 3,
        fillColor: index === 0 ? "#1a73e8" : "#ea4335",
        fillOpacity: 1,
      })
        .bindTooltip(point.label)
        .addTo(layers);
    }
    for (const variant of [...variants].sort(
      (a, b) => Number(b.variant === "fastest") - Number(a.variant === "fastest"),
    )) {
      L.polyline(
        variant.geometry.coordinates.map(
          ([lon, lat]) => [lat, lon] as L.LatLngTuple,
        ),
        {
          color: variant.variant === "fastest" ? "#b45309" : "#1a73e8",
          weight: variant.variant === "fastest" ? 9 : 5,
          dashArray: variant.variant === "constrained" ? "10 6" : undefined,
        },
      )
        .bindTooltip(
          translate(
            variant.variant === "fastest"
              ? "Najszybsza trasa"
              : "Trasa z uwzględnieniem ograniczeń",
          ),
        )
        .addTo(layers);
    }
    if (route && route.coordinates.length >= 2) {
      const points: L.LatLngTuple[] = route.coordinates.map(([lon, lat]) => [
        lat,
        lon,
      ]);
      if (!variants.length) {
        L.polyline(points, { color: "white", weight: 9 }).addTo(layers);
        if (segments?.length) {
          for (const segment of segments) {
            L.polyline(
              segment.geometry.coordinates.map(
                ([lon, lat]) => [lat, lon] as L.LatLngTuple,
              ),
              {
                color:
                  segment.mode === "transit"
                    ? "#087f5b"
                    : segment.mode === "car"
                      ? "#7851a9"
                      : "#1a73e8",
                weight: 5,
                dashArray:
                  segment.mode === "walk" &&
                  segments.some((s) => s.mode === "transit")
                    ? "7 7"
                    : undefined,
              },
            ).addTo(layers);
          }
        } else L.polyline(points, { color: "#1a73e8", weight: 5 }).addTo(layers);
      }
      for (const [index, point] of [
        points[0],
        points[points.length - 1],
      ].entries()) {
        L.circleMarker(point, {
          radius: 7,
          color: "white",
          weight: 3,
          fillColor: index === 0 ? "#1a73e8" : "#ea4335",
          fillOpacity: 1,
        }).addTo(layers);
      }
    }
    const bounds = layers.getBounds();
    boundsRef.current = bounds.isValid() ? bounds : null;
    if (bounds.isValid())
      map.fitBounds(bounds, { padding: [60, 60], maxZoom: 15, animate: false });
    else map.setView(center, 14);
    return () => {
      layers.remove();
    };
  }, [
    places,
    selectedPlaceId,
    route,
    routeVariants,
    endpoints,
    userLocation,
    segments,
  ]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const layers = L.layerGroup().addTo(map);
    const draw = () => {
      layers.clearLayers();
      const bounds = map.getBounds().pad(0.1);
      for (const point of mobility) {
        const { lat, lon } = point.location;
        if (
          !Number.isFinite(lat) ||
          !Number.isFinite(lon) ||
          !bounds.contains([lat, lon])
        )
          continue;
        if (point.kind === "stop" && map.getZoom() < 13) continue;
        const icon = L.divIcon({
          className: `mobility-marker mobility-${point.kind}`,
          html:
            point.kind === "parking"
              ? '<span aria-hidden="true">P ♿</span>'
              : point.kind === "vehicle"
                ? '<span aria-hidden="true">🚌</span>'
                : '<span aria-hidden="true">●</span>',
          iconSize: point.kind === "stop" ? [24, 24] : [34, 28],
        });
        const popup = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = point.name;
        popup.append(title);
        if (point.kind === "parking")
          popup.append(
            document.createElement("br"),
            "Miejsce OZN — brak informacji o zajętości.",
          );
        if (point.updated_at)
          popup.append(
            document.createElement("br"),
            `Aktualizacja: ${new Date(point.updated_at).toLocaleTimeString("pl-PL")}`,
          );
        L.marker([lat, lon], { icon, title: point.name, alt: point.name })
          .bindPopup(popup)
          .addTo(layers);
      }
    };
    draw();
    map.on("moveend", draw);
    return () => {
      map.off("moveend", draw);
      layers.remove();
    };
  }, [mobility]);

  function resetView() {
    const map = mapRef.current;
    if (!map) return;
    if (boundsRef.current)
      map.fitBounds(boundsRef.current, {
        padding: [60, 60],
        maxZoom: 15,
        animate: false,
      });
    else map.setView(center, 14, { animate: false });
  }

  useEffect(() => {
    if (active) popupClose.current?.focus();
  }, [active?.id]);

  function closeDetails() {
    setSelected(null);
    if (markerTrigger.current?.isConnected) markerTrigger.current.focus();
    else container.current?.focus();
  }

  function selectCenter() {
    const point = mapRef.current?.getCenter();
    if (point) onSelectPoint?.({ lat: point.lat, lon: point.lng });
  }

  return (
    <div className="map-region">
      <p id={helpId} className="map-help small">
        Przesuwaj mapę strzałkami lub przyciskami. Powiększaj klawiszami + i −
        albo przyciskami.
        {onSelectPoint &&
          " Wybierz punkt w środku mapy klawiszem Enter. Escape anuluje wybór."}
      </p>
      <div className={`map-view ${onSelectPoint ? "map-picking" : ""}`}>
        <div
          ref={container}
          className="map-canvas"
          role="region"
          tabIndex={0}
          aria-label="Interaktywna mapa Krakowa"
          aria-describedby={helpId}
          onKeyDown={(event) => {
          if (event.key === "Escape" && nativePopup.current?.isOpen()) {
            event.preventDefault();
            mapRef.current?.closePopup();
              return;
            }
            if (event.target !== event.currentTarget || !onSelectPoint) return;
            if (event.key === "Enter") {
              event.preventDefault();
              selectCenter();
            } else if (event.key === "Escape") {
              event.preventDefault();
              onCancelSelection?.();
            }
          }}
        />
        {onSelectPoint && (
          <span className="map-crosshair" aria-hidden="true">
            +
          </span>
        )}
        <button
          type="button"
          className="map-reset"
          aria-label="Przywróć widok mapy"
          onClick={resetView}
        >
          <LocateFixed size={22} />
        </button>
        {tileError && (
          <div className="map-tile-error" role="status">
            Nie udało się pobrać części mapy. Sprawdź połączenie z internetem.
          </div>
        )}
      </div>
      {variants.length > 0 && (
        <p className="small route-map-legend">
          {variants.some((variant) => variant.variant === "fastest") && (
            <span style={{ color: "#b45309" }}>━ Najszybsza trasa </span>
          )}
          {variants.some((variant) => variant.variant === "constrained") && (
            <span style={{ color: "#1a73e8" }}>
              ┄ Trasa z uwzględnieniem ograniczeń
            </span>
          )}
        </p>
      )}
      <div className="map-tools" role="group" aria-label="Przesuwanie mapy">
        {[
          { label: "Przesuń mapę na północ", delta: [0, -120], Icon: ArrowUp },
          {
            label: "Przesuń mapę na zachód",
            delta: [-120, 0],
            Icon: ArrowLeft,
          },
          {
            label: "Przesuń mapę na wschód",
            delta: [120, 0],
            Icon: ArrowRight,
          },
          {
            label: "Przesuń mapę na południe",
            delta: [0, 120],
            Icon: ArrowDown,
          },
        ].map(({ label, delta, Icon }) => (
          <button
            key={label}
            type="button"
            className="icon-button"
            aria-label={label}
            onClick={() =>
              mapRef.current?.panBy(delta as [number, number], {
                animate: false,
              })
            }
          >
            <Icon size={20} aria-hidden="true" />
          </button>
        ))}
        {onSelectPoint && (
          <button
            type="button"
            className="button primary"
            onClick={selectCenter}
          >
            Wybierz środek mapy
          </button>
        )}
      </div>
      {onSelectPoint && (
        <p role="status" className="small">
          Środek mapy: {mapCenter.lat.toFixed(5)}, {mapCenter.lon.toFixed(5)}
        </p>
      )}
      {mobility.length > 0 && (
        <details className="map-data">
          <summary>
            Przystanki, pojazdy i parkingi — lista ({mobility.length})
          </summary>
          <ul>
            {mobility.map((point) => (
              <li key={point.id}>
                <strong>{point.name}</strong>
                {" — "}
                {point.kind === "parking"
                  ? "Miejsce OZN — brak informacji o zajętości."
                  : point.kind === "vehicle"
                    ? "Pojazd komunikacji miejskiej"
                    : "Przystanek"}
                {point.updated_at &&
                  ` · Aktualizacja: ${new Date(point.updated_at).toLocaleTimeString("pl-PL")}`}
                <button
                  type="button"
                  className="text-button"
                  aria-label={`Pokaż na mapie: ${point.name}`}
                  onClick={() => {
                    mapRef.current?.setView(
                      [point.location.lat, point.location.lon],
                      16,
                      { animate: false },
                    );
                    container.current?.focus();
                  }}
                >
                  Pokaż na mapie
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
      {active && (
        <div
          className="map-popup"
          role="region"
          aria-label={active.name}
          onKeyDown={(event) => {
            if (event.key === "Escape") closeDetails();
          }}
        >
          <button
            ref={popupClose}
            type="button"
            className="close"
            aria-label="Zamknij szczegóły znacznika"
            onClick={closeDetails}
          >
            ×
          </button>
          {active.photos?.[0] && (
            <a
              className="map-popup-photo"
              href={active.photos[0].source_url}
              target="_blank"
              rel="noreferrer"
            >
              <img
                src={active.photos[0].url}
                alt={`${active.name} — ${active.photos[0].description?.trim() || active.photos[0].title}`}
                loading="lazy"
              />
              <small>
                {active.photos[0].credit || active.photos[0].author}
              </small>
            </a>
          )}
          <strong>{active.name}</strong>
          <p>
            {active.address && active.address_is_nearest
              ? `${translate("Najbliższy adres:")} ${active.address}`
              : active.address || "Adres nieznany"}
          </p>
          <Link to={`/place/${encodeURIComponent(active.id)}`}>
            Zobacz szczegóły →
          </Link>
        </div>
      )}
    </div>
  );
}
