import type {
  Assessment,
  Constraints,
  Fact,
  Place,
  PlaceSummary,
  Source,
  Report,
} from "./types";

const base = "/api/v1";
let csrfToken: string | null = null;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers.has("Content-Type")
  )
    headers.set("Content-Type", "application/json");
  if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });
  if (response.status === 204) return undefined as T;
  const body = await response.json();
  if (!response.ok)
    throw new ApiError(
      body.error?.code === "INVALID_CREDENTIALS"
        ? "Nieprawidłowy e-mail lub hasło."
        : body.error?.message ||
            `Żądanie nie powiodło się (${response.status}).`,
      response.status,
      body.error?.code || "REQUEST_FAILED",
    );
  return body as T;
}

export type Page<T> = { items: T[]; next_cursor: string | null };
export type PlacePage = Page<PlaceSummary> & {
  total_count: number;
  warnings: string[];
  attribution: Place["attribution"];
};
export type Session = {
  user: { id: string; display_name: string; roles: string[] };
  csrf_token: string;
};
export type Profile = {
  id: string;
  name: string;
  description: string;
  constraints: Constraints;
};
export type RouteGeometry = {
  type: "LineString";
  coordinates: [number, number][];
};
export type PlannedRoute = {
  id: string;
  distance_m: number;
  estimated_duration_s: number | null;
  assessment: Assessment;
  geometry: RouteGeometry;
  computed_at: string;
  facts: Fact[];
  segments: {
    id: string;
    distance_m: number;
    instruction: string;
    geometry: RouteGeometry;
    assessment: Assessment;
    facts: Fact[];
    barriers: { id: string; description: string }[];
    rest_points: { id: string; description: string }[];
    temporary_difficulties: { id: string; description: string }[];
  }[];
};
export type RoutePlan = {
  routes: PlannedRoute[];
  warnings: string[];
  attribution: Source[];
};

export type RouteEndpoint = string | { lat: number; lon: number };
export function searchRoutePoints(
  query: string,
  signal?: AbortSignal,
): Promise<Page<PlaceSummary>> {
  return api(`/routes/points?query=${encodeURIComponent(query)}`, { signal });
}

export function planRoute(
  origin: RouteEndpoint,
  destination: RouteEndpoint,
  constraints: Constraints,
  signal?: AbortSignal,
): Promise<RoutePlan> {
  return api("/routes/plan", {
    method: "POST",
    body: JSON.stringify({
      origin: typeof origin === "string" ? { place_id: origin } : origin,
      destination:
        typeof destination === "string"
          ? { place_id: destination }
          : destination,
      constraints,
    }),
    signal,
  });
}

export async function searchPlaces(
  query: string,
  constraints: Constraints,
  cursor?: string | null,
  near?: { lat: number; lon: number } | null,
  limit = 50,
): Promise<PlacePage> {
  return api("/places/search", {
    method: "POST",
    body: JSON.stringify({
      query: query || "*",
      constraints,
      include_uncertain: true,
      limit,
      cursor,
      ...(near ? { near, radius_m: 20000 } : {}),
    }),
  });
}

export function getPlace(id: string): Promise<Place> {
  return api(`/places/${encodeURIComponent(id)}`);
}

export async function login(email: string, password: string): Promise<Session> {
  const session = await api<Session>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  csrfToken = session.csrf_token;
  return session;
}

export async function register(
  email: string,
  password: string,
  display_name: string,
): Promise<void> {
  await api("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name }),
  });
}

export async function restoreSession(): Promise<Session | null> {
  try {
    const session = await api<Session>("/auth/session");
    csrfToken = session.csrf_token;
    return session;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      csrfToken = null;
      return null;
    }
    throw error;
  }
}

export async function logout(): Promise<void> {
  await api("/auth/logout", { method: "POST" });
  csrfToken = null;
}

export async function listAll<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  let cursor: string | null = null;
  do {
    const page: Page<T> = await api(
      `${path}${path.includes("?") ? "&" : "?"}limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    );
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return items;
}

export type Interpretation = {
  constraints: Constraints;
  summary: string;
  questions: string[];
  requires_confirmation: true;
};
export const interpretNeeds = (description: string) =>
  api<Interpretation>("/needs/interpret", {
    method: "POST",
    body: JSON.stringify({ description }),
  });

export const saveNeedsProfile = (
  id: string | undefined,
  description: string,
  constraints: Constraints,
) =>
  api<Profile>(id ? `/profiles/${encodeURIComponent(id)}` : "/profiles", {
    method: id ? "PATCH" : "POST",
    body: JSON.stringify({
      name: "Mój profil potrzeb",
      description,
      constraints,
    }),
  });

export type Photo = {
  id: string;
  status: "processing" | "ready" | "rejected";
  preview_url: string | null;
  error_code: string | null;
};
export async function uploadPhoto(file: File): Promise<string> {
  if (
    !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
    file.size > 10 * 1024 * 1024
  )
    throw new Error("Dodaj zdjęcie JPEG, PNG lub WebP o rozmiarze do 10 MiB.");
  const data = new FormData();
  data.append("file", file);
  const created = await api<{ id: string; status: "ready" | "processing" }>(
    "/photos",
    { method: "POST", body: data },
  );
  return created.id;
}

export async function withPhoto<T>(
  file: File | null,
  submit: (ids: string[]) => Promise<T>,
): Promise<T> {
  const id = file ? await uploadPhoto(file) : null;
  try {
    return await submit(id ? [id] : []);
  } catch (error) {
    // A photo linked by a successful submission cannot be deleted after a lost response.
    if (id)
      await api(`/photos/${encodeURIComponent(id)}`, {
        method: "DELETE",
      }).catch(() => {});
    throw error;
  }
}

export type ReportInput = Pick<Report, "target" | "kind"> &
  Partial<
    Pick<
      Report,
      "fact_id" | "description" | "observations" | "observed_at" | "photo_ids"
    >
  >;
export const createReport = (body: ReportInput) =>
  api<Report>("/reports", { method: "POST", body: JSON.stringify(body) });
export const getReport = (id: string) =>
  api<Report>(`/reports/${encodeURIComponent(id)}`);
export const reviewReport = (
  id: string,
  decision: "accepted" | "rejected",
  comment: string,
) =>
  api<Report>(`/reports/${encodeURIComponent(id)}/review`, {
    method: "POST",
    body: JSON.stringify({ decision, comment }),
  });

export type Mission = {
  id: string;
  place_id: string;
  place_name: string;
  title: string;
  fact_id: string;
  attribute: Fact["attribute"];
  points: number;
  time_minutes: number;
};
export type MissionProgress = {
  id: string;
  mission_id: string;
  user_id: string;
  status: "in_progress" | "pending" | "accepted" | "rejected";
  report_id: string | null;
  answer: string;
  awarded_points: number;
  review_comment: string | null;
  created_at: string;
  updated_at: string;
};
export type MissionActivity = { items: MissionProgress[]; points: number };
export const getMissions = () => api<Mission[]>("/missions");
export const getMission = (id: string) =>
  api<Mission>(`/missions/${encodeURIComponent(id)}`);
export const requestVerificationMission = (place_id: string, fact_ids: string[]) =>
  api<Mission[]>("/missions/verification-requests", {
    method: "POST",
    body: JSON.stringify({ place_id, fact_ids }),
  });
export const getMissionActivity = () =>
  api<MissionActivity>("/missions/progress");
export const startMission = (id: string) =>
  api<MissionProgress>(`/missions/${encodeURIComponent(id)}/start`, {
    method: "POST",
  });
export const submitMission = (
  id: string,
  description: string,
  photo_ids: string[],
) =>
  api<MissionProgress>(`/missions/${encodeURIComponent(id)}/submit`, {
    method: "POST",
    body: JSON.stringify({ description, photo_ids }),
  });
export const reviewMission = (
  id: string,
  decision: "accepted" | "rejected",
  comment: string,
) =>
  api<MissionProgress>(`/missions/progress/${encodeURIComponent(id)}/review`, {
    method: "POST",
    body: JSON.stringify({ decision, comment }),
  });
