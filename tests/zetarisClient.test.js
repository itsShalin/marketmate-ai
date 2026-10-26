
const test = require("node:test");
const assert = require("node:assert/strict");

const { query } = require("../services/zetarisClient");

const originalEnv = { ...process.env };
const originalFetch = global.fetch;

function configureZetaris() {
  process.env.ZETARIS_BASE_URL = "http://127.0.0.1:8888";
  process.env.ZETARIS_JWT = "test-token";
  process.env.ZETARIS_ORG_ID = "123";
}

test.beforeEach(() => {
  configureZetaris();
});

test.afterEach(() => {
  global.fetch = originalFetch;

  for (const key of [
    "ZETARIS_BASE_URL",
    "ZETARIS_JWT",
    "ZETARIS_ORG_ID",
  ]) {
    if (Object.hasOwn(originalEnv, key)) {
      process.env[key] = originalEnv[key];
    } else {
      delete process.env[key];
    }
  }
});

test("query sends required headers and returns records", async () => {
  const records = [
    { product_id: "prod_lavender_001", name: "Lavender Calm Candle" },
  ];

  let capturedRequest;

  global.fetch = async (url, options) => {
    capturedRequest = { url, options };

    return {
      ok: true,
      status: 200,
      json: async () => ({ records }),
    };
  };

  const result = await query(
    "SELECT * FROM marketmate_data.products LIMIT 10"
  );

  assert.deepEqual(result, records);
  assert.equal(
    capturedRequest.url,
    "http://127.0.0.1:8888/api/v1.0/query/sql/start"
  );
  assert.equal(capturedRequest.options.method, "POST");
  assert.equal(
    capturedRequest.options.headers.Authorization,
    "Bearer test-token"
  );
  assert.equal(capturedRequest.options.headers["X-Org-ID"], "123");
  assert.ok(capturedRequest.options.headers["X-Request-ID"]);
  assert.equal(
    capturedRequest.options.headers["Content-Type"],
    "application/json"
  );

  const body = JSON.parse(capturedRequest.options.body);
  assert.equal(
    body.select,
    "SELECT * FROM marketmate_data.products LIMIT 10"
  );
  assert.equal(body.pageLimit, 100);
});

test("query rejects an empty SQL query", async () => {
  await assert.rejects(query("  "), {
    name: "TypeError",
    message: "A non-empty SQL query is required.",
  });
});

test("query rejects missing configuration", async () => {
  delete process.env.ZETARIS_JWT;

  await assert.rejects(query("SELECT 1"), {
    message: "Zetaris configuration is incomplete.",
  });
});

test("query rejects a non-numeric organisation ID", async () => {
  process.env.ZETARIS_ORG_ID = "not-numeric";

  await assert.rejects(query("SELECT 1"), {
    message: "ZETARIS_ORG_ID must be numeric.",
  });
});

test("query reports HTTP errors", async () => {
  global.fetch = async () => ({
    ok: false,
    status: 401,
  });

  await assert.rejects(query("SELECT 1"), {
    message: "Zetaris returned HTTP 401.",
  });
});

test("query rejects invalid JSON", async () => {
  global.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => {
      throw new SyntaxError("Invalid JSON");
    },
  });

  await assert.rejects(query("SELECT 1"), {
    message: "Zetaris returned invalid JSON.",
  });
});

test("query rejects responses without records", async () => {
  global.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({ results: [] }),
  });

  await assert.rejects(query("SELECT 1"), {
    message: "Zetaris response is missing the records array.",
  });
});

test("query rejects an invalid page limit", async () => {
  await assert.rejects(query("SELECT 1", { pageLimit: 0 }), {
    name: "TypeError",
    message: "pageLimit must be a positive integer.",
  });
});

test("query reports request timeouts", async () => {
  global.fetch = async (_url, options) =>
    new Promise((resolve, reject) => {
      options.signal.addEventListener(
        "abort",
        () => {
          const error = new Error("Aborted");
          error.name = "AbortError";
          reject(error);
        },
        { once: true }
      );
    });

  await assert.rejects(
    query("SELECT 1", { timeoutMs: 20 }),
    { message: "Zetaris request timed out." }
  );
});
