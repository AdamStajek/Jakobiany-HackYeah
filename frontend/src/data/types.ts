export type Attribute =
  | "steps_count"
  | "steps_present"
  | "threshold_height_cm"
  | "kerb_height_cm"
  | "raised_kerb"
  | "lighting_available"
  | "smoothness"
  | "entrance_width_cm"
  | "slope_percent"
  | "ramp_available"
  | "elevator_available"
  | "accessible_toilet"
  | "rest_area_available"
  | "surface"
  | "distance_without_rest_m";
export type Source = {
  type: "owner" | "user" | "osm" | "ai" | "weather" | "other";
  label: string;
  url: string | null;
  license: string | null;
  retrieved_at: string;
  modified_at?: string | null;
};
export type Fact = {
  id: string;
  attribute: Attribute;
  value: number | boolean | string | null;
  unit: string | null;
  status: "confirmed" | "unconfirmed";
  confidence_score: number;
  confidence_level: "certain" | "probable" | "uncertain";
  confidence_calculated_at: string | null;
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
  require_lighting?: boolean | null;
  max_kerb_height_cm?: number | null;
  allowed_smoothness?: string[] | null;
};
export type Assessment = {
  status: "meets_requirements" | "does_not_meet_requirements" | "uncertain";
  summary: string;
  reasons: { code: string; message: string; fact_ids: string[] }[];
};
export type PlaceSummary = {
  id: string;
  is_example?: boolean;
  name: string;
  category: string;
  address: string | null;
  address_is_nearest?: boolean;
  location: { lat: number; lon: number };
  distance_m: number | null;
  assessment?: Assessment;
  facts?: Fact[];
  website?: string | null;
  phone?: string | null;
  opening_hours?: string | null;
  operator?: string | null;
  access?: string | null;
  photos?: PlacePhoto[];
};
export type PlacePhoto = {
  url: string;
  original_url: string;
  source_url: string;
  title: string;
  author: string;
  credit: string;
  license: string;
  license_url: string | null;
  description: string;
};
export type Place = PlaceSummary & {
  photos?: PlacePhoto[];
  facts: Fact[];
  updated_at: string;
  attribution: Source[];
  barriers: { id: string; description: string }[];
  demo?: { image: string; description: string; map_position: [number, number] };
  website_title?: string | null;
  website_description?: string | null;
  website_telephone?: string | null;
  website_opening_hours?: string | null;
  accessibility_summary?: string | null;
  website_source?: Source | null;
};
export type Report = {
  id: string;
  author_id: string;
  target: { type: "place" | "segment"; id: string };
  kind: "correction" | "confirmation" | "missing_data";
  fact_id: string | null;
  description: string | null;
  observations: { attribute: Attribute; value: Fact["value"] }[];
  status: "pending" | "accepted" | "rejected";
  observed_at: string | null;
  photo_ids: string[];
  review_comment: string | null;
  created_at: string;
  updated_at: string;
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
