import { translate } from "../i18n";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getMissions, type Mission } from "../data/api";
import { useDemo } from "../state/DemoContext";

const notificationKey = (userId: string, missionId: string) =>
  `nearby-mission-notified:${userId}:${missionId}`;

export function NearbyMissions() {
  const { session, location, setLocation, activity, notify } = useDemo();
  const route = useLocation();
  const navigate = useNavigate();
  const [enabled, setEnabled] = useState(false);
  const [missions, setMissions] = useState<Mission[]>([]);
  const seen = useRef(new Set<string>());
  useEffect(() => {
    setEnabled(false);
    setMissions([]);
    seen.current.clear();
  }, [session?.user.id]);
  useEffect(() => {
    if (!session || !enabled || !location) return;
    let active = true;
    const refresh = () =>
      getMissions(location)
        .then((items) => {
          if (active) setMissions(items);
        })
        .catch(() => {
          if (active) notify("Nie udało się odświeżyć misji w okolicy.");
        });
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [session?.user.id, enabled, location?.lat, location?.lon]);
  useEffect(() => {
    if (
      !session ||
      !enabled ||
      !location ||
      Notification.permission !== "granted"
    )
      return;
    const candidate = missions.find((mission) => {
      let notifiedThisVisit = seen.current.has(mission.id);
      try {
        notifiedThisVisit ||=
          sessionStorage.getItem(notificationKey(session.user.id, mission.id)) ===
          "1";
      } catch {
        // Keep the in-memory guard if session storage is unavailable.
      }
      if (
        !mission.available ||
        !mission.location ||
        notifiedThisVisit
      )
        return false;
      if (activity.items.some((item) => item.mission_id === mission.id))
        return false;
      const rad = Math.PI / 180;
      const lat = (mission.location.lat - location.lat) * rad;
      const lon = (mission.location.lon - location.lon) * rad;
      const a =
        Math.sin(lat / 2) ** 2 +
        Math.cos(location.lat * rad) *
          Math.cos(mission.location.lat * rad) *
          Math.sin(lon / 2) ** 2;
      return 6371000 * 2 * Math.asin(Math.sqrt(Math.min(1, a))) <= 150;
    });
    if (!candidate) return;
    try {
      const notification = new Notification(translate("Mały krok, wielka pomoc!"), {
        body: `${translate("Jesteś blisko:")} ${candidate.place_name}. ${translate("Sprawdź miejsce i zdobądź")} ${candidate.points} ${translate("punktów!")}`,
        tag: candidate.place_id,
      });
      seen.current.add(candidate.id);
      try {
        sessionStorage.setItem(
          notificationKey(session.user.id, candidate.id),
          "1",
        );
      } catch {
        // The in-memory guard still prevents repeat notifications this mount.
      }
      notification.onclick = () => {
        window.focus();
        navigate(`/missions/${encodeURIComponent(candidate.id)}`);
        notification.close();
      };
    } catch {
      setEnabled(false);
      notify(
        "Ta przeglądarka nie obsługuje powiadomień. Misje znajdziesz na liście.",
      );
    }
  }, [session, enabled, location, missions, activity.items, navigate]);
  if (!session || route.pathname !== "/missions") return null;
  return (
    <div className="page narrow nearby-missions">
      <button
        className="button subtle"
        aria-pressed={enabled}
        onClick={async () => {
          if (enabled) {
            setEnabled(false);
            return;
          }
          if (!("Notification" in window) || !navigator.geolocation) {
            notify("Przeglądarka nie obsługuje lokalizacji lub powiadomień.");
            return;
          }
          try {
            const permission = await Notification.requestPermission();
            if (permission !== "granted") {
              notify(
                "Powiadomienia są zablokowane. Możesz zmienić zgodę w ustawieniach przeglądarki.",
              );
              return;
            }
            navigator.geolocation.getCurrentPosition(
              ({ coords }) => {
                setLocation({ lat: coords.latitude, lon: coords.longitude });
                setEnabled(true);
              },
              () => {
                notify("Udostępnij lokalizację, aby wykrywać misje w pobliżu.");
              },
              { timeout: 10000, maximumAge: 60000 },
            );
          } catch {
            notify("Nie udało się włączyć powiadomień.");
          }
        }}
      >
        {enabled
          ? "Wyłącz powiadomienia o misjach"
          : "Włącz powiadomienia o misjach w pobliżu"}
      </button>
      <p className="muted">
        Powiadomimy Cię o misji w promieniu 150 m, gdy aplikacja będzie otwarta.
        Wymagana jest zgoda na lokalizację i powiadomienia.
      </p>
    </div>
  );
}
