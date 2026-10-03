import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LocateFixed } from "lucide-react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { RouteGeometry } from "../data/api";
import type { PlaceSummary } from "../data/types";
import { translate, useLanguage } from "../i18n";

const noEndpoints: { lat: number; lon: number; label: string }[] = [];
const center: L.LatLngTuple = [50.061, 19.936];
export default function MapView({
  places,
  route,
  onSelectPoint,
  endpoints = noEndpoints,
  userLocation,
}: {
  places: PlaceSummary[];
  route?: RouteGeometry;
  onSelectPoint?: (point: { lat: number; lon: number }) => void;
  endpoints?: { lat: number; lon: number; label: string }[];
  userLocation?: { lat: number; lon: number } | null;
}) {
  const language = useLanguage();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const boundsRef = useRef<L.LatLngBounds | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [tileError, setTileError] = useState(false);
  const active = places.find((place) => place.id === selected);

  useEffect(() => {
    if (!container.current) return;
    const map = L.map(container.current, { zoomControl: false }).setView(
      center,
      14,
    );
    mapRef.current = map;
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
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      maxNativeZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    })
      .on("tileerror", () => setTileError(true))
      .on("tileload", () => setTileError(false))
      .addTo(map);
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
        className: "place-marker",
        html: '<span class="place-marker-pin" aria-hidden="true"></span>',
        iconSize: [36, 44],
        iconAnchor: [18, 44],
      });
      const marker = L.marker([lat, lon], {
        icon,
        title: `${translate("Pokaż na mapie:")} ${place.name}`,
        alt: place.name,
      })
        .on("click", () => setSelected(place.id))
        .addTo(layers);
      marker
        .getElement()
        ?.setAttribute("aria-label", `${translate("Pokaż na mapie:")} ${place.name}`);
    }
    if (userLocation && Number.isFinite(userLocation.lat) && Number.isFinite(userLocation.lon)) {
      L.circleMarker([userLocation.lat, userLocation.lon], {
        radius: 9,
        color: "white",
        weight: 3,
        fillColor: "#1a73e8",
        fillOpacity: 1,
      }).bindTooltip("Twoja lokalizacja").addTo(layers);
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
    if (route && route.coordinates.length >= 2) {
      const points: L.LatLngTuple[] = route.coordinates.map(([lon, lat]) => [
        lat,
        lon,
      ]);
      L.polyline(points, { color: "white", weight: 9 }).addTo(layers);
      L.polyline(points, { color: "#1a73e8", weight: 5 }).addTo(layers);
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
  }, [places, route, endpoints, userLocation]);

  function resetView() {
    const map = mapRef.current;
    if (!map) return;
    if (boundsRef.current)
      map.fitBounds(boundsRef.current, { padding: [60, 60], maxZoom: 15 });
    else map.setView(center, 14);
  }

  return (
    <div className={`map-view ${onSelectPoint ? "map-picking" : ""}`}>
      <div
        ref={container}
        className="map-canvas"
        aria-label="Interaktywna mapa Krakowa"
      />
      <button
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
      {active && (
        <div className="map-popup">
          <button
            className="close"
            aria-label="Zamknij szczegóły znacznika"
            onClick={() => setSelected(null)}
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
                alt={`${active.name} — ${active.photos[0].title}`}
                loading="lazy"
              />
              <small>{active.photos[0].credit || active.photos[0].author}</small>
            </a>
          )}
          <strong>{active.name}</strong>
          <p>{active.address && active.address_is_nearest ? `${translate("Najbliższy adres:")} ${active.address}` : active.address || "Adres nieznany"}</p>
          <Link to={`/place/${encodeURIComponent(active.id)}`}>
            Zobacz szczegóły →
          </Link>
        </div>
      )}
    </div>
  );
}
