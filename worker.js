// FrodoTappins cumulative sync. Apply schema.sql before deploying.
// Both endpoints require X-API-Key. Old full-history clients remain supported.
const FIELDS = ["keystrokes", "words", "deletions", "alt_tabs", "power_cycles"];
const MAX_BODY = 2 * 1024 * 1024;

class BadRequest extends Error {}

export default {
  async fetch(request, env) {
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type,X-API-Key,Authorization",
      "Cache-Control": "no-store",
    };
    if (request.method === "OPTIONS") return new Response(null, {headers: cors});
    const key = request.headers.get("X-API-Key") ||
      (request.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
    if (!env.API_KEY || key !== env.API_KEY) return json({error: "unauthorized"}, 401, cors);
    try {
      const path = new URL(request.url).pathname;
      if (request.method === "POST" && path === "/sync") {
        return await sync(request, env.DB, cors);
      }
      if (request.method === "GET" && path === "/totals") {
        return json(await totals(env.DB), 200, cors);
      }
      return json({error: "not found"}, 404, cors);
    } catch (error) {
      if (error instanceof BadRequest || error instanceof SyntaxError) {
        return json({error: error.message}, 400, cors);
      }
      return json({error: "Cloud database unavailable. Retry the sync."}, 503, cors);
    }
  },
};

function json(value, status, headers) {
  return new Response(JSON.stringify(value), {status, headers: {
    ...headers, "Content-Type": "application/json",
  }});
}

function counts(value, allowMissing = false) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new BadRequest("Missing cumulative counts.");
  }
  const result = {};
  for (const field of FIELDS) {
    const n = value[field] === undefined && allowMissing ? 0 : value[field];
    if (!Number.isSafeInteger(n) || n < 0) throw new BadRequest(`Invalid ${field} count.`);
    result[field] = n;
  }
  return result;
}

async function readBody(request) {
  // Enforce the bound while streaming, not after allocating the whole request.
  const reader = request.body?.getReader();
  if (!reader) throw new BadRequest("Missing request body.");
  let size = 0;
  const chunks = [];
  for (;;) {
    const {value, done} = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY) {
      await reader.cancel();
      throw new BadRequest("Sync payload exceeds 2 MiB.");
    }
    chunks.push(value);
  }
  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
  return JSON.parse(new TextDecoder().decode(body));
}

async function sync(request, db, cors) {
  const body = await readBody(request);
  if (!body || typeof body !== "object" || Array.isArray(body)) throw new BadRequest("Invalid payload.");
  const id = body.device_id;
  const name = body.device_name;
  if (typeof id !== "string" || !/^[A-Za-z0-9_-]{1,64}$/.test(id) ||
      typeof name !== "string" || name.length > 128) throw new BadRequest("Invalid device identity.");
  let value, expected, legacyDays;
  if (body.protocol === 2) {
    value = counts(body.totals);
    expected = body.expected_revision;
    if (!Number.isSafeInteger(expected) || expected < 0) throw new BadRequest("Invalid revision.");
  } else if (body.protocol === undefined && Array.isArray(body.days)) {
    // Old clients send their complete local history. Collapse it without storing
    // or rewriting daily rows. Lower/stale totals are rejected just like v2.
    if (!body.days.length || body.days.length > 5000) throw new BadRequest("Invalid daily history length.");
    const dates = new Set();
    value = Object.fromEntries(FIELDS.map(field => [field, 0]));
    for (const row of body.days) {
      if (!row || typeof row.day !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(row.day) ||
          !Number.isFinite(Date.parse(row.day)) ||
          new Date(row.day).toISOString().slice(0, 10) !== row.day || dates.has(row.day)) {
        throw new BadRequest("Invalid or duplicate history date.");
      }
      dates.add(row.day);
      const day = counts(row, true);
      for (const field of FIELDS) value[field] += day[field];
    }
    value = counts(value);
    legacyDays = body.days.length;
    const previous = await db.prepare("SELECT revision FROM device_totals WHERE device_id = ?").bind(id).first();
    expected = previous?.revision || 0;
  } else {
    throw new BadRequest("Unsupported sync protocol.");
  }
  const now = new Date();
  const timestamp = now.toISOString();
  const today = timestamp.slice(0, 10);
  const cutoff = new Date(now.getTime() - 6 * 86400000).toISOString().slice(0, 10);
  const syncId = crypto.randomUUID();
  const update = db.prepare(`
    INSERT INTO device_totals
      (device_id, device_name, keystrokes, words, deletions, alt_tabs, power_cycles,
       revision, sync_id, updated_at)
    SELECT ?, ?, ?, ?, ?, ?, ?, 1, ?, ?
    WHERE ? = 0 OR EXISTS (SELECT 1 FROM device_totals WHERE device_id = ?)
    ON CONFLICT(device_id) DO UPDATE SET
      device_name = excluded.device_name, keystrokes = excluded.keystrokes,
      words = excluded.words, deletions = excluded.deletions,
      alt_tabs = excluded.alt_tabs, power_cycles = excluded.power_cycles,
      revision = device_totals.revision + 1,
      sync_id = excluded.sync_id, updated_at = excluded.updated_at
    WHERE device_totals.revision = ?
      AND excluded.keystrokes >= device_totals.keystrokes
      AND excluded.words >= device_totals.words
      AND excluded.deletions >= device_totals.deletions
      AND excluded.alt_tabs >= device_totals.alt_tabs
      AND excluded.power_cycles >= device_totals.power_cycles
    RETURNING revision
  `).bind(id, name, ...FIELDS.map(field => value[field]), syncId, timestamp, expected, id, expected);
  const snapshot = db.prepare(`
    INSERT INTO device_snapshots
      (device_id, snapshot_day, device_name, keystrokes, words, deletions,
       alt_tabs, power_cycles, revision, updated_at)
    SELECT device_id, ?, device_name, keystrokes, words, deletions, alt_tabs,
           power_cycles, revision, updated_at FROM device_totals
    WHERE device_id = ? AND sync_id = ?
    ON CONFLICT(device_id, snapshot_day) DO UPDATE SET
      device_name = excluded.device_name, keystrokes = excluded.keystrokes,
      words = excluded.words, deletions = excluded.deletions,
      alt_tabs = excluded.alt_tabs, power_cycles = excluded.power_cycles,
      revision = excluded.revision, updated_at = excluded.updated_at
  `).bind(today, id, syncId);
  const prune = db.prepare(`DELETE FROM device_snapshots WHERE snapshot_day < ?
    AND EXISTS (SELECT 1 FROM device_totals WHERE device_id = ? AND sync_id = ?)
  `).bind(cutoff, id, syncId);
  // D1 batches are transactions. Snapshot/pruning only proceed if this exact
  // request won the optimistic concurrency check; neither can record a loser.
  const results = await db.batch([update, snapshot, prune]);
  const revision = results[0].results?.[0]?.revision;
  if (!revision) return json({error: "Cloud history is newer or larger than this upload. Refresh and reconcile local data before retrying.", code: "sync_conflict"}, 409, cors);
  return json({ok: true, protocol: 2, revision, rows: legacyDays ?? 1}, 200, cors);
}

async function totals(db) {
  const result = await db.prepare(`SELECT device_id, device_name, keystrokes,
    words, deletions, alt_tabs, power_cycles, revision, updated_at
    FROM device_totals ORDER BY keystrokes DESC, device_id`).all();
  const devices = result.results || [];
  const global = Object.fromEntries(FIELDS.map(field => [field, 0]));
  for (const device of devices) for (const field of FIELDS) {
    global[field] += device[field];
    if (!Number.isSafeInteger(global[field]) || global[field] < 0) {
      throw new Error("Combined totals exceed supported count range.");
    }
  }
  return {protocol: 2, global, device_count: devices.length, devices};
}
