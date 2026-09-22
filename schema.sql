-- Cumulative totals, one row per installation. Existing daily stats are local.
CREATE TABLE IF NOT EXISTS device_totals (
  device_id TEXT PRIMARY KEY,
  device_name TEXT NOT NULL,
  keystrokes INTEGER NOT NULL CHECK (keystrokes >= 0),
  words INTEGER NOT NULL CHECK (words >= 0),
  deletions INTEGER NOT NULL CHECK (deletions >= 0),
  alt_tabs INTEGER NOT NULL CHECK (alt_tabs >= 0),
  power_cycles INTEGER NOT NULL CHECK (power_cycles >= 0),
  revision INTEGER NOT NULL CHECK (revision >= 1),
  sync_id TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Last accepted cumulative totals for each UTC date, retained for seven days.
CREATE TABLE IF NOT EXISTS device_snapshots (
  device_id TEXT NOT NULL,
  snapshot_day TEXT NOT NULL,
  device_name TEXT NOT NULL,
  keystrokes INTEGER NOT NULL,
  words INTEGER NOT NULL,
  deletions INTEGER NOT NULL,
  alt_tabs INTEGER NOT NULL,
  power_cycles INTEGER NOT NULL,
  revision INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (device_id, snapshot_day)
);
CREATE INDEX IF NOT EXISTS idx_device_snapshots_day ON device_snapshots(snapshot_day);
