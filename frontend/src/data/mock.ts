import type {
  Attribute,
  Constraints,
  Fact,
  Place,
  Source,
  Assessment,
} from "./types";
const date = "2026-10-02T10:00:00Z";
export const sources: Source[] = [
  {
    type: "owner",
    label: "Deklaracja właściciela",
    url: null,
    license: null,
    retrieved_at: date,
  },
  {
    type: "user",
    label: "Potwierdzenie użytkownika",
    url: null,
    license: null,
    retrieved_at: date,
  },
  {
    type: "osm",
    label: "OpenStreetMap",
    url: "https://www.openstreetmap.org/copyright",
    license: "ODbL",
    retrieved_at: date,
  },
];
const values: [Attribute, Fact["value"], string | null][] = [
  ["steps_count", 0, "count"],
  ["threshold_height_cm", 0, "cm"],
  ["entrance_width_cm", 96, "cm"],
  ["slope_percent", 4, "percent"],
  ["ramp_available", true, null],
  ["elevator_available", false, null],
  ["accessible_toilet", true, null],
  ["rest_area_available", true, null],
  ["surface", "paved", null],
  ["distance_without_rest_m", 200, "m"],
];
function facts(id: string, issue?: Fact["unconfirmed_reason"]): Fact[] {
  return values.map(([attribute, value, unit], i) => {
    const problem = attribute === "accessible_toilet" && issue;
    return {
      id: `${id}_${attribute}`,
      attribute,
      value: problem ? null : value,
      unit,
      status: problem ? "unconfirmed" : "confirmed",
      confidence_score: problem ? 5 : i % 2 ? 8 : 15,
      confidence_level: problem ? "uncertain" : i % 2 ? "probable" : "certain",
      confidence_calculated_at: date,
      confidence_percent: problem ? null : i % 2 ? 88 : 95,
      observed_at:
        problem === "missing"
          ? null
          : problem === "stale"
            ? "2026-02-01T10:00:00Z"
            : date,
      updated_at: date,
      valid_until: null,
      sources: problem === "missing" ? [] : [sources[i % 2]],
      unconfirmed_reason: problem || null,
      ...(problem === "conflicting"
        ? {
            alternatives: [
              { value: true, source: sources[0], observed_at: date },
              { value: false, source: sources[1], observed_at: date },
            ],
          }
        : {}),
    };
  });
}
export const places: Place[] = [
  {
    id: "pod-wawelem",
    name: "Kawiarnia Pod Wawelem",
    category: "Restauracje i kawiarnie",
    address: "ul. Bernardyńska 2, Kraków",
    location: { lat: 50.0536, lon: 19.937 },
    distance_m: 650,
    facts: facts("pod-wawelem"),
    updated_at: date,
    attribution: sources.slice(0, 2),
    barriers: [],
    demo: {
      image: "cafe",
      description:
        "Spokojne miejsce na kawę i chwilę odpoczynku. Wejście od strony ulicy, stoliki także na zewnątrz.",
      map_position: [45, 67],
    },
  },
  {
    id: "cafe-lisboa",
    name: "Café Lisboa",
    category: "Restauracje i kawiarnie",
    address: "ul. Dolnych Młynów 3, Kraków",
    location: { lat: 50.065, lon: 19.927 },
    distance_m: 1100,
    facts: facts("cafe-lisboa", "conflicting"),
    updated_at: date,
    attribution: sources.slice(0, 2),
    barriers: [],
    demo: {
      image: "cafe",
      description:
        "Kawa i portugalskie wypieki. Informacje o toalecie wymagają ponownego sprawdzenia.",
      map_position: [28, 30],
    },
  },
  {
    id: "muzeum",
    name: "Muzeum Narodowe",
    category: "Atrakcje turystyczne",
    address: "al. 3 Maja 1, Kraków",
    location: { lat: 50.06, lon: 19.923 },
    distance_m: 1400,
    facts: facts("muzeum", "missing"),
    updated_at: date,
    attribution: sources.slice(0, 2),
    barriers: [],
    demo: {
      image: "museum",
      description:
        "Miejsce spotkania ze sztuką. Brakuje potwierdzonych danych o toalecie.",
      map_position: [16, 50],
    },
  },
  {
    id: "park",
    name: "Park Jordana",
    category: "Parki i tereny zielone",
    address: "al. 3 Maja, Kraków",
    location: { lat: 50.064, lon: 19.915 },
    distance_m: 1900,
    facts: facts("park", "stale"),
    updated_at: date,
    attribution: sources.slice(0, 2),
    barriers: [],
    demo: {
      image: "park",
      description:
        "Zielone alejki, ławki i przestrzeń na spokojny spacer. Dane o toalecie są nieaktualne.",
      map_position: [12, 24],
    },
  },
  {
    id: "toaleta",
    name: "Toaleta przy Plantach",
    category: "Toalety publiczne",
    address: "ul. Podzamcze, Kraków",
    location: { lat: 50.055, lon: 19.934 },
    distance_m: 800,
    facts: facts("toaleta"),
    updated_at: date,
    attribution: sources.slice(0, 2),
    barriers: [],
    demo: {
      image: "museum",
      description:
        "Obiekt z informacjami o szerokości wejścia i braku stopni.",
      map_position: [37, 58],
    },
  },
  {
    id: "przychodnia",
    name: "Przychodnia przy Rynku",
    category: "Przychodnie i szpitale",
    address: "ul. Szewska 8, Kraków",
    location: { lat: 50.063, lon: 19.934 },
    distance_m: 900,
    facts: facts("przychodnia"),
    updated_at: date,
    attribution: sources.slice(0, 2),
    barriers: [],
    demo: {
      image: "museum",
      description:
        "Przychodnia z wejściem bez progu i miejscami do siedzenia.",
      map_position: [43, 37],
    },
  },
];
export const labels: Partial<Record<Attribute, string>> = {
  steps_count: "Schody",
  steps_present: "Stopnie",
  threshold_height_cm: "Próg wejściowy",
  kerb_height_cm: "Wysokość krawężnika",
  raised_kerb: "Podniesiony krawężnik",
  lighting_available: "Oświetlenie",
  smoothness: "Równość nawierzchni",
  entrance_width_cm: "Szerokość wejścia",
  slope_percent: "Nachylenie podjazdu",
  ramp_available: "Podjazd",
  elevator_available: "Winda",
  accessible_toilet: "Toaleta dostępna",
  rest_area_available: "Miejsca do siedzenia",
  surface: "Nawierzchnia",
  distance_without_rest_m: "Odległość bez odpoczynku",
};
export const reasonLabels = {
  missing: "Brak potwierdzonych danych",
  conflicting: "Źródła podają różne informacje",
  stale: "Informacja może być nieaktualna",
  pending_verification: "Oczekuje na weryfikację",
};
export function formatFact(f: Fact): string {
  if (f.status === "unconfirmed")
    return reasonLabels[f.unconfirmed_reason || "missing"];
  if (f.value === null) return reasonLabels.missing;
  if (f.attribute === "steps_count" && typeof f.value === "number")
    return `${f.value} ${
      f.value === 1
        ? "stopień"
        : f.value % 10 >= 2 &&
            f.value % 10 <= 4 &&
            (f.value % 100 < 12 || f.value % 100 > 14)
          ? "stopnie"
          : "stopni"
    }`;
  if (
    ["threshold_height_cm", "kerb_height_cm"].includes(f.attribute) &&
    typeof f.value === "number"
  )
    return f.value <= 2
      ? "Accessible for wheelchairs"
      : "Inaccessible for wheelchairs";
  if (f.attribute === "entrance_width_cm" && typeof f.value === "number")
    return f.value >= 90
      ? "Accessible for wheelchairs"
      : "Inaccessible for wheelchairs";
  if (typeof f.value === "boolean") return f.value ? "Tak" : "Nie";
  if (f.attribute === "surface")
    return (
      { paved: "Utwardzona", asphalt: "Asfalt", cobblestone: "Kostka brukowa" }[
        String(f.value)
      ] || String(f.value)
    );
  return `${f.value} ${f.unit === "percent" ? "%" : f.unit || ""}`;
}
// Lokalna ocena używana dla danych bez oceny z API.
export function assess(place: Place, c: Constraints): Assessment {
  const checks: [Attribute, (value: NonNullable<Fact["value"]>) => boolean][] =
    [];
  const max = (attr: Attribute, n: number | null) => {
    if (n !== null) checks.push([attr, (v) => typeof v === "number" && v <= n]);
  };
  max("steps_count", c.require_step_free_access ? 0 : c.max_steps);
  max("threshold_height_cm", c.max_threshold_cm);
  max("slope_percent", c.max_slope_percent);
  max("distance_without_rest_m", c.max_distance_without_rest_m);
  if (c.min_entrance_width_cm !== null)
    checks.push([
      "entrance_width_cm",
      (v) => typeof v === "number" && v >= c.min_entrance_width_cm!,
    ]);
  if (c.require_accessible_toilet)
    checks.push(["accessible_toilet", (v) => v === true]);
  if (c.allowed_surfaces)
    checks.push(["surface", (v) => c.allowed_surfaces!.includes(String(v))]);
  const reasons: Assessment["reasons"] = [];
  let failed = false;
  for (const [attribute, check] of checks) {
    const f = place.facts.find((f) => f.attribute === attribute);
    if (!f || f.status !== "confirmed" || f.value === null)
      reasons.push({
        code: "UNCONFIRMED",
        message: `${labels[attribute]}: ${f ? formatFact(f) : reasonLabels.missing}`,
        fact_ids: f ? [f.id] : [],
      });
    else if (!check(f.value)) {
      failed = true;
      reasons.push({
        code: "REQUIREMENT_NOT_MET",
        message: `${labels[attribute]}: ${formatFact(f)}`,
        fact_ids: [f.id],
      });
    }
  }
  return {
    status: failed
      ? "does_not_meet_requirements"
      : !checks.length || reasons.length
        ? "uncertain"
        : "meets_requirements",
    summary: failed
      ? "Nie spełnia podanych wymagań"
      : !checks.length
        ? "Wybierz potrzeby, aby sprawdzić dopasowanie"
        : reasons.length
          ? "Brakuje pewnych informacji"
          : "Dobrze dopasowane do Twoich potrzeb",
    reasons,
  };
}
export const routeSteps = [
  {
    street: "ul. Pawia",
    instruction: "Idź prosto ulicą Pawią w stronę Plant.",
    distance: 350,
    surface: "Utwardzona",
    slope: 2,
    rest: "Ławka przy wejściu na Planty",
    warning: null,
  },
  {
    street: "Planty",
    instruction: "Skręć w prawo i idź alejką przez Planty.",
    distance: 450,
    surface: "Brak potwierdzonych danych",
    slope: 3,
    rest: "Dwie ławki przy alejce",
    warning: "Na odcinku 150 m nie potwierdzono nawierzchni.",
  },
  {
    street: "ul. Bernardyńska",
    instruction:
      "Skręć w lewo w ulicę Bernardyńską. Cel znajduje się po prawej stronie.",
    distance: 400,
    surface: "Utwardzona",
    slope: 4,
    rest: "Ławka przy celu",
    warning: null,
  },
];
export const missions = [
  {
    id: "toaleta",
    place: "park",
    title: "Sprawdź dostępność toalety w Parku Jordana",
    points: 50,
    time: 10,
  },
  {
    id: "wejscie",
    place: "muzeum",
    title: "Potwierdź informacje o wejściu do muzeum",
    points: 30,
    time: 5,
  },
  {
    id: "podjazd",
    place: "cafe-lisboa",
    title: "Sprawdź podjazd przy Café Lisboa",
    points: 20,
    time: 5,
  },
];
