
const crypto = require("node:crypto");

const DEFAULT_TIMEOUT_MS = 15_000;

function getConfig() {
  const { ZETARIS_BASE_URL, ZETARIS_JWT, ZETARIS_ORG_ID } = process.env;

  if (!ZETARIS_BASE_URL || !ZETARIS_JWT || !ZETARIS_ORG_ID) {
    throw new Error("Zetaris configuration is incomplete.");
  }

  if (!/^\d+$/.test(ZETARIS_ORG_ID)) {
    throw new Error("ZETARIS_ORG_ID must be numeric.");
  }

  return {
    baseUrl: ZETARIS_BASE_URL.replace(/\/+$/, ""),
    jwt: ZETARIS_JWT,
    orgId: ZETARIS_ORG_ID,
  };
}

async function query(sql, options = {}) {
  if (typeof sql !== "string" || !sql.trim()) {
    throw new TypeError("A non-empty SQL query is required.");
  }

  const config = getConfig();
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const pageLimit = options.pageLimit ?? 100;

  if (!Number.isInteger(timeoutMs) || timeoutMs <= 0) {
    throw new TypeError("timeoutMs must be a positive integer.");
  }

  if (!Number.isInteger(pageLimit) || pageLimit <= 0) {
    throw new TypeError("pageLimit must be a positive integer.");
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(
      `${config.baseUrl}/api/v1.0/query/sql/start`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${config.jwt}`,
          "X-Org-ID": config.orgId,
          "X-Request-ID": crypto.randomUUID(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          select: sql.trim(),
          pageLimit,
        }),
        signal: controller.signal,
      }
    );

    if (!response.ok) {
      const errorBody = await response.text();
    
      console.error("Zetaris request failed:", {
        status: response.status,
        statusText: response.statusText,
        responseBody: errorBody,
      });
    
      throw new Error(`Zetaris returned HTTP ${response.status}.`);
    }

    let payload;

    try {
      payload = await response.json();
    } catch {
      throw new Error("Zetaris returned invalid JSON.");
    }

    if (!payload || !Array.isArray(payload.records)) {
      throw new Error("Zetaris response is missing the records array.");
    }

    return payload.records;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("Zetaris request timed out.");
    }

    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

module.exports = { query };
