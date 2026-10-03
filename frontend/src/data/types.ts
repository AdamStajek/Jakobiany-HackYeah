export type Attribute =
  | "steps_count"
  | "threshold_height_cm"
  | "entrance_width_cm"
  | "slope_percent"
  | "ramp_available"
  | "elevator_available"
  | "accessible_toilet"
  | "rest_area_available"
  | "surface"
  | "distance_without_rest_m";
export type Source = {
  type: "owner" | "user" | "osm";
  label: string;
  url: string | null;
  license: string | null;
  retrieved_at: string;
};
export type Fact = {
  id: string;
  attribute: Attribute;
  value: number | boolean | string | null;
  unit: string | null;
  status: "confirmed" | "unconfirmed";
  confidence_percent: number | null;
  observed_at: string | null;
  updated_at: string;
  valid_until: string | null;
  sources: Source[];
  unconfirmed_reason:
    "missing" | "conflicting" | "stale" | "pending_verification" | null;
  alternatives?: {
    value: number | boolean | string;
    source: Source;
    observed_at: string;
  }[];
};
export type Constraints = {
  max_steps: number | null;
  max_threshold_cm: number | null;
  max_slope_percent: number | null;
  min_entrance_width_cm: number | null;
  max_distance_without_rest_m: number | null;
  require_step_free_access: boolean | null;
  require_accessible_toilet: boolean | null;
  allowed_surfaces: string[] | null;
};
export type Assessment = {
  status: "meets_requirements" | "does_not_meet_requirements" | "uncertain";
  summary: string;
  reasons: { code: string; message: string; fact_ids: string[] }[];
};
export type Place = {
  id: string;
  name: string;
  category: string;
  address: string;
  location: { lat: number; lon: number };
  distance_m: number;
  facts: Fact[];
  updated_at: string;
  attribution: Source[];
  barriers: { id: string; description: string }[];
  demo: { image: string; description: string; map_position: [number, number] };
};
export type Report = {
  id: string;
  target: { type: "place"; id: string };
  kind: "correction" | "confirmation" | "missing_data";
  fact_id: string | null;
  description: string;
  observations: { attribute: Attribute; value: Fact["value"] }[];
  status: "pending";
  observed_at: string;
  demo_photo_name: string | null;
};
export const emptyConstraints: Constraints = {
  max_steps: null,
  max_threshold_cm: null,
  max_slope_percent: null,
  min_entrance_width_cm: null,
  max_distance_without_rest_m: null,
  require_step_free_access: null,
  require_accessible_toilet: null,
  allowed_surfaces: null,
};
