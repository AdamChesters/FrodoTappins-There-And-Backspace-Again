-- Apply schema.sql first. This additive backfill preserves the legacy stats table.
-- Repeat after switching the Worker to reconcile any final legacy-client writes.
INSERT INTO device_totals
  (device_id, device_name, keystrokes, words, deletions, alt_tabs, power_cycles,
   revision, sync_id, updated_at)
SELECT s.device_id,
       COALESCE((SELECT device_name FROM stats n WHERE n.device_id = s.device_id
                 ORDER BY day DESC, updated_at DESC LIMIT 1), ''),
       SUM(s.keystrokes), SUM(s.words), SUM(s.deletions), SUM(s.alt_tabs),
       SUM(s.power_cycles), 1, 'legacy-migration', MAX(s.updated_at)
FROM stats s WHERE 1 GROUP BY s.device_id
ON CONFLICT(device_id) DO UPDATE SET
  keystrokes = MAX(device_totals.keystrokes, excluded.keystrokes),
  words = MAX(device_totals.words, excluded.words),
  deletions = MAX(device_totals.deletions, excluded.deletions),
  alt_tabs = MAX(device_totals.alt_tabs, excluded.alt_tabs),
  power_cycles = MAX(device_totals.power_cycles, excluded.power_cycles),
  revision = device_totals.revision + 1,
  sync_id = 'legacy-migration',
  updated_at = MAX(device_totals.updated_at, excluded.updated_at)
WHERE excluded.keystrokes > device_totals.keystrokes
   OR excluded.words > device_totals.words
   OR excluded.deletions > device_totals.deletions
   OR excluded.alt_tabs > device_totals.alt_tabs
   OR excluded.power_cycles > device_totals.power_cycles;

INSERT INTO device_snapshots
  (device_id, snapshot_day, device_name, keystrokes, words, deletions, alt_tabs,
   power_cycles, revision, updated_at)
SELECT device_id, date('now'), device_name, keystrokes, words, deletions,
       alt_tabs, power_cycles, revision, updated_at FROM device_totals WHERE 1
ON CONFLICT(device_id, snapshot_day) DO UPDATE SET
  device_name = excluded.device_name, keystrokes = excluded.keystrokes,
  words = excluded.words, deletions = excluded.deletions,
  alt_tabs = excluded.alt_tabs, power_cycles = excluded.power_cycles,
  revision = excluded.revision, updated_at = excluded.updated_at
WHERE excluded.revision > device_snapshots.revision;
