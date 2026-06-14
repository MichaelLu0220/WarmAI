PRAGMA foreign_keys = ON;

CREATE TABLE inference_events (
    request_id TEXT PRIMARY KEY,
    client_request_id TEXT NOT NULL,
    raw_text_masked TEXT NOT NULL,
    raw_model_output_masked TEXT NOT NULL,
    response_json_masked TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    pii_detected INTEGER NOT NULL CHECK (pii_detected IN (0, 1)),
    training_eligible INTEGER NOT NULL CHECK (training_eligible IN (0, 1)),
    model_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
    validation_result TEXT NOT NULL,
    fallback_stage TEXT NOT NULL,
    recovered_fields_json TEXT NOT NULL,
    defaulted_fields_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE idempotency_records (
    idempotency_key TEXT PRIMARY KEY,
    input_hash TEXT NOT NULL,
    request_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed')),
    pii_detected INTEGER NOT NULL DEFAULT 0 CHECK (pii_detected IN (0, 1)),
    response_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE TABLE dataset_candidates (
    candidate_id TEXT PRIMARY KEY,
    inference_request_id TEXT REFERENCES inference_events(request_id),
    source TEXT NOT NULL,
    synthetic INTEGER NOT NULL CHECK (synthetic IN (0, 1)),
    status TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'rejected', 'needs_review')),
    training_eligible INTEGER NOT NULL CHECK (training_eligible IN (0, 1)),
    rejected_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE teacher_votes (
    vote_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES dataset_candidates(candidate_id),
    teacher_raw_output_masked TEXT NOT NULL,
    teacher_model_version TEXT NOT NULL,
    teacher_prompt_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE model_registry (
    model_version TEXT PRIMARY KEY,
    base_model TEXT NOT NULL,
    dataset_version TEXT,
    dataset_hash TEXT,
    evaluation_json TEXT NOT NULL,
    deployment_alias TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
