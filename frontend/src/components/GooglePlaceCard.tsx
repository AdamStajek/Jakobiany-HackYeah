import { useEffect, useRef, useState } from "react";
import type { PlaceSummary } from "../data/types";

declare const __GOOGLE_MAPS_BROWSER_KEY__: string;
type GoogleWindow = Window & {
  google?: { maps: { importLibrary: (name: string) => Promise<unknown> } };
  swojaDrogaGoogleReady?: () => void;
};
let library: Promise<unknown> | undefined;

function loadPlaces() {
  if (library) return library;
  const target = window as GoogleWindow;
  library = new Promise<void>((resolve, reject) => {
    if (target.google?.maps.importLibrary) return resolve();
    const script = document.createElement("script");
    const timer = window.setTimeout(() => reject(new Error("timeout")), 20000);
    target.swojaDrogaGoogleReady = () => {
      window.clearTimeout(timer);
      delete target.swojaDrogaGoogleReady;
      resolve();
    };
    script.onerror = () => {
      window.clearTimeout(timer);
      reject(new Error("network"));
    };
    const params = new URLSearchParams({
      key: __GOOGLE_MAPS_BROWSER_KEY__,
      v: "weekly",
      loading: "async",
      language: "pl",
      region: "PL",
      callback: "swojaDrogaGoogleReady",
    });
    script.src = `https://maps.googleapis.com/maps/api/js?${params}`;
    script.async = true;
    document.head.append(script);
  }).then(() => target.google!.maps.importLibrary("places"));
  return library;
}

export default function GooglePlaceCard({ place }: { place: PlaceSummary }) {
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState("");
  useEffect(() => {
    if (!__GOOGLE_MAPS_BROWSER_KEY__) return;
    let cancelled = false;
    const host = container.current!;
    setStatus("Ładowanie informacji Google Maps…");
    const failed = () => {
      if (!cancelled)
        setStatus("Informacje Google Maps są chwilowo niedostępne.");
    };
    let timer = window.setTimeout(failed, 25000);
    loadPlaces()
      .then(() => {
        if (cancelled) return;
        const details = document.createElement("gmp-place-details");
        const request = document.createElement(
          "gmp-place-details-location-request",
        );
        request.setAttribute(
          "location",
          `${place.location.lat},${place.location.lon}`,
        );
        details.append(request, document.createElement("gmp-place-all-content"));
        details.addEventListener("gmp-error", failed);
        details.addEventListener("gmp-load", () => {
          window.clearTimeout(timer);
          if (!cancelled) setStatus("");
        });
        setStatus("Ładowanie karty Google Maps…");
        host.replaceChildren(details);
      })
      .catch(failed);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      host.replaceChildren();
    };
  }, [place]);

  return (
    <section className="google-place-card" aria-label="Informacje Google Maps">
      {!__GOOGLE_MAPS_BROWSER_KEY__ && (
        <p>Informacje Google Maps są obecnie niedostępne.</p>
      )}
      {status && <p role="status">{status}</p>}
      <div ref={container} data-no-translate />
    </section>
  );
}
