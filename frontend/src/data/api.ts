import type { Constraints, Place, PlaceSummary } from "./types";

const base = "/api/v1";
let csrfToken: string | null = null;

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type"))
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
    throw new Error(
      body.error?.message || `Żądanie nie powiodło się (${response.status}).`,
    );
  return body as T;
}

export type Page<T> = { items: T[]; next_cursor: string | null };
export type PlacePage = Page<PlaceSummary> & {
  warnings: string[];
  attribution: Place["attribution"];
};
export type Session = {
  user: { id: string; display_name: string };
  csrf_token: string;
};
export type Profile = {
  id: string;
  name: string;
  description: string;
  constraints: Constraints;
};
export type RoutePlan = {
  routes: {
    id: string;
    distance_m: number;
    estimated_duration_s: number | null;
    assessment: Place["assessment"];
    segments: {
      id: string;
      distance_m: number;
      instruction: string;
      assessment: Place["assessment"];
    }[];
  }[];
  warnings: string[];
};

export async function searchPlaces(
  query: string,
  constraints: Constraints,
): Promise<PlacePage> {
  return api("/places/search", {
    method: "POST",
    body: JSON.stringify({
      query: query || "*",
      constraints,
      include_uncertain: true,
      limit: 50,
      near: { lat: 50.0614, lon: 19.9366 },
      radius_m: 20000,
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
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  await api("/auth/logout", { method: "POST" });
  csrfToken = null;
}
