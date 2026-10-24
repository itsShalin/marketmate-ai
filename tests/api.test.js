
const test = require("node:test");
const assert = require("node:assert/strict");

const express = require("express");
const request = require("node:http");

const app = express();
app.use(express.json());

app.post("/test/business", (req, res) => {
  const { businessId, message } = req.body;

  if (
    typeof businessId !== "string" ||
    !businessId.trim() ||
    typeof message !== "string" ||
    !message.trim()
  ) {
    return res.status(400).json({
      success: false,
      message: "businessId and message are required.",
    });
  }

  if (businessId !== "biz_cozy_candles_001") {
    return res.status(404).json({
      success: false,
      message: "Business not found.",
    });
  }

  return res.status(200).json({
    success: true,
    businessId,
  });
});

test("API rejects missing business ID", async () => {
  const server = app.listen(0);

  try {
    const { port } = server.address();

    const response = await fetch(`http://127.0.0.1:${port}/test/business`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "Suggest a marketing idea" }),
    });

    assert.equal(response.status, 400);
    assert.equal((await response.json()).success, false);
  } finally {
    await new Promise((resolve, reject) => {
      server.close((error) => error ? reject(error) : resolve());
    });
  }
});
