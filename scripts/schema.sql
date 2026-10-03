PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL CHECK (json_valid(value_json))
);
CREATE TABLE categories (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL
);
CREATE TABLE osm_objects (
    id TEXT PRIMARY KEY,
    osm_type TEXT NOT NULL CHECK (osm_type IN ('node', 'way', 'relation')),
    osm_id INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    license TEXT NOT NULL DEFAULT 'ODbL',
    modified_at TEXT,
    version INTEGER,
    tags_json TEXT NOT NULL CHECK (json_valid(tags_json)),
    geometry_json TEXT NOT NULL CHECK (json_valid(geometry_json)),
    UNIQUE (osm_type, osm_id)
);
CREATE TABLE places (
    id TEXT PRIMARY KEY REFERENCES osm_objects(id),
    name TEXT,
    lat REAL NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon REAL NOT NULL CHECK (lon BETWEEN -180 AND 180),
    street TEXT,
    housenumber TEXT,
    postcode TEXT,
    city TEXT,
    address_unit TEXT,
    website TEXT,
    phone TEXT,
    opening_hours TEXT,
    operator TEXT,
    access TEXT
);
CREATE TABLE place_web_data (
    place_id TEXT PRIMARY KEY REFERENCES places(id),
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    title TEXT,
    description TEXT,
    telephone TEXT,
    opening_hours TEXT,
    accessibility_summary TEXT
);
CREATE TABLE place_categories (
    place_id TEXT NOT NULL REFERENCES places(id),
    category_id TEXT NOT NULL REFERENCES categories(id),
    PRIMARY KEY (place_id, category_id)
);
CREATE TABLE place_features (
    place_id TEXT NOT NULL REFERENCES places(id),
    object_id TEXT NOT NULL REFERENCES osm_objects(id),
    link_method TEXT NOT NULL CHECK (link_method IN ('entrance_on_outline', 'within_place', 'building_context')),
    PRIMARY KEY (place_id, object_id)
);
CREATE TABLE accessibility_facts (
    place_id TEXT NOT NULL REFERENCES places(id),
    attribute TEXT NOT NULL,
    value_json TEXT CHECK (value_json IS NULL OR json_valid(value_json)),
    unit TEXT,
    status TEXT NOT NULL DEFAULT 'unconfirmed' CHECK (status = 'unconfirmed'),
    unconfirmed_reason TEXT NOT NULL CHECK (unconfirmed_reason IN ('missing', 'conflicting', 'pending_verification')),
    confidence_percent REAL CHECK (confidence_percent IS NULL),
    observed_at TEXT CHECK (observed_at IS NULL),
    PRIMARY KEY (place_id, attribute)
);
CREATE TABLE fact_evidence (
    place_id TEXT NOT NULL,
    attribute TEXT NOT NULL,
    object_id TEXT NOT NULL REFERENCES osm_objects(id),
    tag_key TEXT NOT NULL,
    raw_value TEXT NOT NULL,
    parsed_value_json TEXT NOT NULL CHECK (json_valid(parsed_value_json)),
    scope TEXT NOT NULL,
    method TEXT NOT NULL CHECK (method IN ('tag', 'explicit_description', 'mapped_feature')),
    FOREIGN KEY (place_id, attribute) REFERENCES accessibility_facts(place_id, attribute),
    PRIMARY KEY (place_id, attribute, object_id, tag_key, scope)
);
CREATE INDEX idx_places_location ON places(lat, lon);
CREATE INDEX idx_categories_places ON place_categories(category_id);
CREATE INDEX idx_facts_attribute ON accessibility_facts(attribute);

CREATE VIEW place_accessibility AS
SELECT p.*,
    MAX(CASE WHEN f.attribute = 'steps_count' THEN json_extract(f.value_json, '$') END) AS steps_count,
    MAX(CASE WHEN f.attribute = 'threshold_height_cm' THEN json_extract(f.value_json, '$') END) AS threshold_height_cm,
    MAX(CASE WHEN f.attribute = 'elevator_available' THEN json_extract(f.value_json, '$') END) AS elevator_available,
    MAX(CASE WHEN f.attribute = 'entrance_width_cm' THEN json_extract(f.value_json, '$') END) AS entrance_width_cm,
    MAX(CASE WHEN f.attribute = 'accessible_toilet' THEN json_extract(f.value_json, '$') END) AS accessible_toilet,
    MAX(CASE WHEN f.attribute = 'wheelchair' THEN json_extract(f.value_json, '$') END) AS wheelchair
FROM places p JOIN accessibility_facts f ON p.id = f.place_id
GROUP BY p.id;
