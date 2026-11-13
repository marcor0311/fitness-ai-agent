// Persistent inbox in D1: acknowledge storage first, then fetch Hevy separately.
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const clock = () => Math.floor(Date.now() / 1000);

function json(body, status = 200, headers = {}) {
  return Response.json(body, { status, headers: { "Cache-Control": "no-store", ...headers } });
}

async function authorized(request, expected) {
  if (!expected || expected.length < 32) return false;
  const incoming = request.headers.get("Authorization") || "";
  if (incoming.length > 1024) return false;
  const encoder = new TextEncoder();
  const [left, right] = await Promise.all([incoming, expected].map(async value =>
    new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(value)))));
  let different = 0;
  for (let i = 0; i < left.length; i++) different |= left[i] ^ right[i];
  return different === 0;
}

async function smallJson(request) {
  if (!request.headers.get("Content-Type")?.toLowerCase().startsWith("application/json")) {
    throw { status: 415 };
  }
  if (Number(request.headers.get("Content-Length")) > 4096) throw { status: 413 };
  const reader = request.body?.getReader();
  if (!reader) throw { status: 400 };
  let timer;
  try {
    return await Promise.race([
      (async () => {
        const chunks = [];
        let size = 0;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > 4096) throw { status: 413 };
          chunks.push(value);
        }
        const bytes = new Uint8Array(size);
        let offset = 0;
        for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
        return JSON.parse(new TextDecoder().decode(bytes));
      })(),
      new Promise((_, reject) => { timer = setTimeout(() => reject({ status: 408 }), 1500); }),
    ]);
  } finally {
    clearTimeout(timer);
    await reader.cancel().catch(() => {});
  }
}

export async function processWorkout(env, workoutId, hevyFetch = fetch) {
  const now = clock();
  const token = crypto.randomUUID();
  const claimed = await env.DB.prepare(`
    UPDATE webhook_events SET status = 'processing', attempts = attempts + 1,
      lease_until = ?, lease_token = ?
    WHERE workout_id = ? AND (
      (status = 'pending' AND next_attempt_at <= ?) OR
      (status = 'processing' AND lease_until <= ?)
    ) RETURNING attempts
  `).bind(now + 120, token, workoutId, now, now).first();
  if (!claimed) return;
  let failure = "hevy_unavailable";
  try {
    if (!env.HEVY_API_KEY) { failure = "missing_hevy_api_key"; throw new Error(); }
    const response = await hevyFetch(`https://api.hevyapp.com/v1/workouts/${workoutId}`, {
      method: "GET", headers: { "api-key": env.HEVY_API_KEY, "Accept": "application/json" },
      // Workers supports manual/follow only. The !ok check below rejects 3xx
      // without forwarding the API key to a redirect destination.
      redirect: "manual", signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) { failure = `hevy_http_${response.status}`; throw new Error(); }
    failure = "invalid_hevy_response";
    const data = await response.json();
    const workout = data?.workout || data;
    if (!workout || typeof workout.id !== "string" || workout.id.toLowerCase() !== workoutId
        || typeof workout.title !== "string" || !Array.isArray(workout.exercises)) throw new Error();
    failure = "storage_write_failed";
    // Fence stale consumers: a worker whose lease expired cannot overwrite a newer result.
    await env.DB.batch([
      env.DB.prepare(`INSERT INTO workouts (id, payload_json, stored_at)
        SELECT ?, ?, ? WHERE EXISTS (
          SELECT 1 FROM webhook_events WHERE workout_id = ? AND lease_token = ? AND status = 'processing'
        ) ON CONFLICT(id) DO UPDATE SET payload_json = excluded.payload_json, stored_at = excluded.stored_at
      `).bind(workoutId, JSON.stringify(workout), clock(), workoutId, token),
      env.DB.prepare(`UPDATE webhook_events SET status = 'processed', lease_until = 0,
        lease_token = NULL, last_error = NULL WHERE workout_id = ? AND lease_token = ?
      `).bind(workoutId, token),
    ]);
  } catch {
    const delay = Math.min(3600, 30 * 2 ** Math.min(claimed.attempts - 1, 7));
    await env.DB.prepare(`UPDATE webhook_events SET status = 'pending', next_attempt_at = ?,
      lease_until = 0, lease_token = NULL, last_error = ?
      WHERE workout_id = ? AND lease_token = ?
    `).bind(clock() + delay, failure, workoutId, token).run();
  }
}

async function drain(env) {
  const now = clock();
  const { results } = await env.DB.prepare(`SELECT workout_id FROM webhook_events WHERE
    (status = 'pending' AND next_attempt_at <= ?) OR (status = 'processing' AND lease_until <= ?)
    ORDER BY received_at LIMIT 5
  `).bind(now, now).all();
  for (const row of results) await processWorkout(env, row.workout_id);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") return json({ ok: true });
    if (url.pathname !== "/webhooks/hevy" && url.pathname !== "/api/workouts") return json({ error: "not_found" }, 404);
    const isWebhook = url.pathname === "/webhooks/hevy";
    const method = isWebhook ? "POST" : "GET";
    if (request.method !== method) return json({ error: "method_not_allowed" }, 405, { Allow: method });
    const secret = isWebhook ? env.HEVY_WEBHOOK_AUTH : env.READ_API_AUTH;
    if (!secret || secret.length < 32 || !env.DB) return json({ error: "not_configured" }, 503);
    if (!await authorized(request, secret)) return json({ error: "unauthorized" }, 401);
    try {
      if (isWebhook) {
        let payload;
        try { payload = await smallJson(request); }
        catch (error) { return json({ error: "invalid_body" }, error.status || 400); }
        if (typeof payload?.workoutId !== "string" || !UUID.test(payload.workoutId)) return json({ error: "invalid_workout_id" }, 400);
        const id = payload.workoutId.toLowerCase();
        await env.DB.prepare(`INSERT INTO webhook_events (workout_id, received_at) VALUES (?, ?)
          ON CONFLICT(workout_id) DO NOTHING`).bind(id, clock()).run();
        // Durable insert above is awaited. waitUntil is just the fast path; cron recovers it.
        ctx.waitUntil(processWorkout(env, id).catch(() => console.error("hevy_background_failed")));
        return json({ ok: true }); // Exactly 200; no Hevy/AI calls on the acknowledgement path.
      }
      const cursor = url.searchParams.get("cursor") || "0";
      if (!/^\d{1,15}$/.test(cursor)) return json({ error: "invalid_cursor" }, 400);
      const { results } = await env.DB.prepare(`SELECT sequence, payload_json FROM workouts
        WHERE sequence > ? ORDER BY sequence LIMIT 51
      `).bind(Number(cursor)).all();
      const page = results.slice(0, 50);
      const last = page.at(-1);
      const next = last ? String(last.sequence) : cursor;
      return json({ workouts: page.map(row => JSON.parse(row.payload_json)), cursor: next, has_more: results.length > 50 });
    } catch {
      // Never acknowledge a webhook that could not be persisted, and never log secrets or payloads.
      console.error("hevy_storage_unavailable");
      return json({ error: "storage_unavailable" }, 503);
    }
  },
  async scheduled(_event, env) { await drain(env); },
};
