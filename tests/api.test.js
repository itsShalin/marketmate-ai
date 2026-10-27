
const test = require("node:test");
const assert = require("node:assert/strict");
const app = require("../index");

let server;
let baseUrl;

test.before(async () => {
  server = app.listen(0);

  await new Promise((resolve, reject) => {
    server.once("listening", resolve);
    server.once("error", reject);
  });

  baseUrl = `http://127.0.0.1:${server.address().port}`;
});

test.after(async () => {
  if (!server) return;

  await new Promise((resolve, reject) => {
    server.close((error) => {
      if (error) reject(error);
      else resolve();
    });
  });
});

test("health endpoint confirms the backend is running", async () => {
  const response = await fetch(`${baseUrl}/api/health`);
  const body = await response.json();

  assert.equal(response.status, 200);
  assert.equal(body.success, true);
});

test("business endpoint returns the Cozy Candle Co. profile", async () => {
  const response = await fetch(
    `${baseUrl}/api/business/biz_cozy_candles_001`
  );
  const body = await response.json();

  assert.equal(response.status, 200);
  assert.equal(body.id, "biz_cozy_candles_001");
  assert.ok(body.name);
  assert.ok(body.category);
});

test("business endpoint returns 404 for an unknown business", async () => {
  const response = await fetch(
    `${baseUrl}/api/business/unknown_business`
  );

  assert.equal(response.status, 404);
});

test("products endpoint returns a list of products", async () => {
  const response = await fetch(
    `${baseUrl}/api/business/biz_cozy_candles_001/products`
  );
  const body = await response.json();

  assert.equal(response.status, 200);
  assert.ok(Array.isArray(body.items));
  assert.ok(body.items.length > 0);
  assert.ok(body.items[0].id);
  assert.ok(body.items[0].name);
});

test("inventory endpoint returns stock information", async () => {
  const response = await fetch(
    `${baseUrl}/api/business/biz_cozy_candles_001/inventory`
  );
  const body = await response.json();

  assert.equal(response.status, 200);
  assert.ok(Array.isArray(body.items));
  assert.ok(body.items.length > 0);
  assert.ok("stock" in body.items[0]);
});

test("engagement endpoint returns a list of posts", async () => {
  const response = await fetch(
    `${baseUrl}/api/business/biz_cozy_candles_001/engagement`
  );
  const body = await response.json();

  assert.equal(response.status, 200);
  assert.ok(Array.isArray(body.items));
});

test("agent endpoint rejects a missing business ID", async () => {
  const response = await fetch(`${baseUrl}/api/agent/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request: "Suggest a marketing idea" }),
  });

  assert.equal(response.status, 400);
});

test("agent endpoint rejects an unknown business before calling Python", async () => {
  const response = await fetch(`${baseUrl}/api/agent/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      businessId: "unknown_business",
      request: "Suggest a marketing idea",
    }),
  });

  assert.equal(response.status, 404);
});
