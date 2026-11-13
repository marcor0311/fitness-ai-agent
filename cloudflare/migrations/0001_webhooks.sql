CREATE TABLE webhook_events (
  workout_id TEXT PRIMARY KEY,
  received_at INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'processed')),
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at INTEGER NOT NULL DEFAULT 0,
  lease_until INTEGER NOT NULL DEFAULT 0,
  lease_token TEXT,
  last_error TEXT
);
CREATE INDEX events_pending ON webhook_events(status, next_attempt_at);
CREATE INDEX events_processing ON webhook_events(status, lease_until);

CREATE TABLE workouts (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
  stored_at INTEGER NOT NULL
);
