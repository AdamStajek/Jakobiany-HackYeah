import { useState } from "react";
import { Link } from "react-router-dom";
import { Minus, Plus, MapPin } from "lucide-react";
import type { PlaceSummary } from "../data/types";
export default function MapView({
  places,
  route = false,
}: {
  places: PlaceSummary[];
  route?: boolean;
}) {
  const [zoom, setZoom] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const active = places.find((p) => p.id === selected);
  return (
    <div className="map-view">
      <svg viewBox="0 0 700 650" aria-hidden="true" className="map-drawing">
        <g
          transform={`translate(${350 - 350 * zoom} ${325 - 325 * zoom}) scale(${zoom})`}
        >
          <rect width="700" height="650" fill="#eeeee5" />
          <path
            d="M-50 500Q200 360 320 490T750 550"
            fill="none"
            stroke="#b2dce3"
            strokeWidth="74"
          />
          <path
            d="M130 0Q200 170 100 360L70 440M590 0Q470 150 520 300L650 430"
            fill="none"
            stroke="#d0ddc3"
            strokeWidth="55"
          />
          <ellipse
            cx="365"
            cy="260"
            rx="162"
            ry="202"
            fill="none"
            stroke="#c6d6b9"
            strokeWidth="27"
          />
          {Array.from({ length: 12 }, (_, i) => (
            <g key={i}>
              <path
                d={`M${i * 80 - 180} 0L${i * 80 + 80} 650`}
                stroke="#fff"
                strokeWidth="9"
              />
              <path
                d={`M0 ${i * 65}L700 ${i * 65 + 130}`}
                stroke="#fff"
                strokeWidth="8"
              />
            </g>
          ))}
          <path
            d="M360 35L355 395M210 215L500 205M200 310L480 335"
            stroke="#d6cbb9"
            strokeWidth="16"
            fill="none"
          />
          <rect
            x="295"
            y="196"
            width="120"
            height="94"
            rx="7"
            fill="#e2d7c3"
            stroke="#fff"
            strokeWidth="7"
          />
          <g fill="#b9ccb0">
            <rect x="60" y="130" width="90" height="80" rx="18" />
            <rect x="430" y="475" width="145" height="75" rx="25" />
          </g>
          <g
            fill="#667363"
            fontFamily="sans-serif"
            fontSize="15"
            textAnchor="middle"
          >
            <text x="355" y="247">
              RYNEK GŁÓWNY
            </text>
            <text x="340" y="143">
              STARE MIASTO
            </text>
            <text x="360" y="417">
              WAWEL
            </text>
            <text x="521" y="551">
              KAZIMIERZ
            </text>
            <text
              x="165"
              y="535"
              fill="#427b90"
              transform="rotate(-20 165 535)"
            >
              Wisła
            </text>
            <text x="110" y="172">
              Park Jordana
            </text>
            <text x="550" y="325">
              Planty
            </text>
            <text x="428" y="63">
              Dworzec Główny
            </text>
          </g>
          {route && (
            <>
              <path
                d="M425 83L382 128L390 184L438 261L365 330L315 440"
                stroke="white"
                strokeWidth="12"
                fill="none"
              />
              <path
                d="M425 83L382 128L390 184L438 261L365 330L315 440"
                stroke="#287aba"
                strokeWidth="6"
                strokeLinejoin="round"
                fill="none"
              />
              <circle
                cx="425"
                cy="83"
                r="10"
                fill="#287aba"
                stroke="white"
                strokeWidth="4"
              />
              <circle
                cx="315"
                cy="440"
                r="10"
                fill="#ad572b"
                stroke="white"
                strokeWidth="4"
              />
            </>
          )}
        </g>
      </svg>
      {!route &&
        places.map((p) => (
          <button
            key={p.id}
            className={`map-pin ${p.assessment?.status !== "meets_requirements" ? "uncertain" : ""}`}
            style={{
              left: `${50 + ((p.location.lon - 19.936) * 1800 + 50 - 50) * zoom}%`,
              top: `${50 + (50 - (p.location.lat - 50.061) * 1800 - 50) * zoom}%`,
            }}
            onClick={() => setSelected(p.id)}
            aria-label={`Pokaż na mapie: ${p.name}`}
          >
            <MapPin size={26} />
            <span>
              {(p.facts || []).some((f) => f.status === "unconfirmed")
                ? "?"
                : "✓"}
            </span>
          </button>
        ))}
      {active && (
        <div className="map-popup">
          <button
            className="close"
            aria-label="Zamknij szczegóły znacznika"
            onClick={() => setSelected(null)}
          >
            ×
          </button>
          <strong>{active.name}</strong>
          <p>{active.address || "Adres nieznany"}</p>
          <Link to={`/place/${encodeURIComponent(active.id)}`}>
            Zobacz szczegóły →
          </Link>
        </div>
      )}
      <div className="map-controls">
        <button
          aria-label="Powiększ mapę"
          disabled={zoom >= 1.8}
          onClick={() => setZoom((z) => Math.min(1.8, z + 0.2))}
        >
          <Plus />
        </button>
        <button
          aria-label="Pomniejsz mapę"
          disabled={zoom <= 1}
          onClick={() => setZoom((z) => Math.max(1, z - 0.2))}
        >
          <Minus />
        </button>
      </div>
      <div className="map-caption">
        Mapa poglądowa · współrzędne OpenStreetMap
      </div>
    </div>
  );
}
