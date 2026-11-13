import test from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import worker, { processWorkout } from "../src/worker.mjs";

const ID = "f1085cdb-32b2-4003-967d-53a3af8eaecb";
const AUTH = "Bearer webhook-secret-for-tests-123456789";
const READ = "Bearer separate-read-secret-for-tests-123456789";
const workout = (title = "D - test") => ({ id: ID, title, exercises: [] });

// Actual SQLite queries, with the small async adapter supplied by D1 in production.
function fixture() {
  const sql = new DatabaseSync(":memory:");
  sql.exec(readFileSync(new URL("../migrations/0001_webhooks.sql", import.meta.url), "utf8"));
  function statement(query, args = []) {
    return {
      bind(...values) { return statement(query, values); },
      async first() { return sql.prepare(query).get(...args) || null; },
      async all() { return { results: sql.prepare(query).all(...args) }; },
      async run() { return { success: true, meta: sql.prepare(query).run(...args) }; },
    };
  }
  const env = {
    HEVY_WEBHOOK_AUTH: AUTH, READ_API_AUTH: READ, HEVY_API_KEY: "test-key",
    DB: {
      prepare: statement,
      async batch(statements) {
        sql.exec("BEGIN");
        try {
          const rows = [];
          for (const stmt of statements) rows.push(await stmt.run());
          sql.exec("COMMIT");
          return rows;
        } catch (error) { sql.exec("ROLLBACK"); throw error; }
      },
    },
  };
  const pending = [];
  const ctx = { waitUntil(promise) { pending.push(promise); } };
  const send = (body = { workoutId: ID }, auth = AUTH) => worker.fetch(new Request("https://test/webhooks/hevy", {
    method: "POST", headers: { Authorization: auth, "Content-Type": "application/json" }, body: JSON.stringify(body),
  }), env, ctx);
  const read = (cursor = "0", auth = READ) => worker.fetch(new Request(`https://test/api/workouts?cursor=${cursor}`, {
    headers: { Authorization: auth },
  }), env, ctx);
  return { sql, env, ctx, pending, send, read };
}

test("acknowledges durable storage without waiting for Hevy; then saves the workout", async t => {
  const f = fixture();
  let release;
  const hevy = new Promise(resolve => { release = resolve; });
  t.mock.method(globalThis, "fetch", (url, options) => {
    assert.equal(url, `https://api.hevyapp.com/v1/workouts/${ID}`);
    assert.equal(options.method, "GET");
    assert.equal(options.headers["api-key"], "test-key");
    assert.equal(options.redirect, "manual");
    return hevy;
  });
  const response = await f.send();
  assert.equal(response.status, 200);
  assert.equal(f.sql.prepare("SELECT count(*) AS n FROM webhook_events").get().n, 1);
  assert.equal(f.sql.prepare("SELECT count(*) AS n FROM workouts").get().n, 0);
  release(Response.json(workout()));
  await Promise.all(f.pending);
  assert.equal(f.sql.prepare("SELECT status FROM webhook_events").get().status, "processed");
  assert.deepEqual((await (await f.read()).json()).workouts, [workout()]);
});

test("authentication and malformed payloads cannot create records", async () => {
  const f = fixture();
  assert.equal((await f.send(undefined, "wrong")).status, 401);
  assert.equal((await f.send({ workoutId: "invalid" })).status, 400);
  assert.equal((await f.send({ workoutId: ID, extra: "x".repeat(5000) })).status, 413);
  assert.equal((await f.read("0", AUTH)).status, 401);
  assert.equal(f.sql.prepare("SELECT count(*) AS n FROM webhook_events").get().n, 0);
});

test("database failure never returns 200", async () => {
  const f = fixture();
  f.env.DB.prepare = () => { throw new Error("database offline"); };
  assert.equal((await f.send()).status, 503);
  assert.equal(f.pending.length, 0);
});

test("duplicate notifications do not duplicate workouts or API calls", async t => {
  const f = fixture();
  const mock = t.mock.method(globalThis, "fetch", async () => Response.json({ workout: workout() }));
  await f.send();
  await Promise.all(f.pending);
  await f.send({ workoutId: ID.toUpperCase() });
  await Promise.all(f.pending);
  assert.equal(mock.mock.callCount(), 1);
  assert.equal(f.sql.prepare("SELECT count(*) AS n FROM workouts").get().n, 1);
});

test("cron recovers a saved event even if the first worker never ran its background job", async t => {
  const f = fixture();
  f.sql.prepare("INSERT INTO webhook_events(workout_id, received_at) VALUES(?, 1)").run(ID);
  t.mock.method(globalThis, "fetch", async () => Response.json(workout()));
  await worker.scheduled({}, f.env);
  assert.equal(f.sql.prepare("SELECT status FROM webhook_events").get().status, "processed");
});

test("upstream failure remains durable and is retried later", async t => {
  const f = fixture();
  const mock = t.mock.method(globalThis, "fetch", async () => new Response("private upstream body", { status: 500 }));
  await f.send();
  await Promise.all(f.pending);
  const event = f.sql.prepare("SELECT * FROM webhook_events").get();
  assert.equal(event.status, "pending");
  assert.equal(event.last_error, "hevy_http_500");
  assert.equal(event.attempts, 1);
  assert.ok(event.next_attempt_at > Math.floor(Date.now() / 1000));
  f.sql.exec("UPDATE webhook_events SET next_attempt_at=0");
  mock.mock.mockImplementation(async () => Response.json(workout()));
  await worker.scheduled({}, f.env);
  assert.equal(f.sql.prepare("SELECT status FROM webhook_events").get().status, "processed");
});

test("expired leases cannot overwrite the newer consumer result", async () => {
  const f = fixture();
  f.sql.prepare("INSERT INTO webhook_events(workout_id, received_at) VALUES(?, 1)").run(ID);
  let release;
  const waiting = new Promise(resolve => { release = resolve; });
  const first = processWorkout(f.env, ID, () => waiting);
  // Allow the first claim to finish and its fetch to begin.
  await Promise.resolve();
  f.sql.exec("UPDATE webhook_events SET lease_until=0");
  await processWorkout(f.env, ID, async () => Response.json(workout("new consumer")));
  release(Response.json(workout("stale consumer")));
  await first;
  assert.equal(JSON.parse(f.sql.prepare("SELECT payload_json FROM workouts").get().payload_json).title, "new consumer");
});

test("pagination handles same-time arrivals and rejects invalid cursors", async () => {
  const f = fixture();
  for (let i = 0; i < 51; i++) {
    const value = { ...workout(), id: crypto.randomUUID() };
    f.sql.prepare("INSERT INTO workouts(id,payload_json,stored_at) VALUES(?,?,1)").run(value.id, JSON.stringify(value));
  }
  const first = await (await f.read()).json();
  assert.equal(first.workouts.length, 50);
  assert.equal(first.has_more, true);
  const second = await (await f.read(first.cursor)).json();
  assert.equal(second.workouts.length, 1);
  assert.equal(second.has_more, false);
  assert.equal(new Set([...first.workouts, ...second.workouts].map(w => w.id)).size, 51);
  assert.equal((await f.read("invalid")).status, 400);
});

test("an unexpected Hevy workout is not stored", async () => {
  const f = fixture();
  f.sql.prepare("INSERT INTO webhook_events(workout_id, received_at) VALUES(?,1)").run(ID);
  await processWorkout(f.env, ID, async () => Response.json({ ...workout(), id: crypto.randomUUID() }));
  assert.equal(f.sql.prepare("SELECT count(*) AS n FROM workouts").get().n, 0);
  assert.equal(f.sql.prepare("SELECT last_error FROM webhook_events").get().last_error, "invalid_hevy_response");
});

test("Hevy redirects remain pending without following the redirect or forwarding credentials", async () => {
  const f = fixture();
  f.sql.prepare("INSERT INTO webhook_events(workout_id, received_at) VALUES(?,1)").run(ID);
  let calls = 0;
  await processWorkout(f.env, ID, async (url, options) => {
    calls++;
    assert.equal(url, `https://api.hevyapp.com/v1/workouts/${ID}`);
    assert.equal(options.redirect, "manual");
    return new Response(null, { status: 302, headers: { Location: "https://other.example/" } });
  });
  assert.equal(calls, 1);
  assert.equal(f.sql.prepare("SELECT status FROM webhook_events").get().status, "pending");
  assert.equal(f.sql.prepare("SELECT last_error FROM webhook_events").get().last_error, "hevy_http_302");
  assert.equal(f.sql.prepare("SELECT count(*) AS n FROM workouts").get().n, 0);
});
