require("dotenv").config();
const express = require("express");
const cors = require("cors");
const { findBusinessById } = require("./services/businessRepository");

const app = express();
const PORT = process.env.PORT || 3000;
const AI_SERVICE_URL =
  process.env.AI_SERVICE_URL || "http://localhost:8001";

app.use(cors());
app.use(express.json());

// Check whether the backend is running.
app.get("/api/health", async (req, res) => {
  res.status(200).json({
    success: true,
    message: "MarketMate AI backend is running!",
  });
});

// Forward marketing requests to Roshni's Python AI service.
app.post("/api/agent/run", async (req, res) => {
  const { businessId, request } = req.body || {};

  if (
    typeof businessId !== "string" ||
    !businessId.trim() ||
    typeof request !== "string" ||
    !request.trim()
  ) {
    return res.status(400).json({
      success: false,
      message: "businessId and request are required.",
    });
  }
  const business = await findBusinessById(businessId.trim());
  

  if (!business) {
    return res.status(404).json({
      success: false,
      message: "Business not found.",
    });
  }
  

  try {
    const response = await fetch(`${AI_SERVICE_URL}/run`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        business_id: businessId.trim(),
        request: request.trim(),
      }),
      signal: AbortSignal.timeout(300_000),
    });

    const result = await response.json();

    // Return the AI service's response without changing its structure.
    return res.status(response.status).json(result);
  } catch (error) {
    console.error("AI service request failed:", error.message);

    return res.status(502).json({
      success: false,
      message: "The AI service could not be reached.",
    });
  }
});

// Return the business profile in the format Roshni expects.
app.get("/api/business/:id", async (req, res) => {
  const business = await findBusinessById(req.params.id);

  if (!business) {
    return res.status(404).json({
      message: "Business not found.",
    });
  }

  return res.json({
    id: business.businessId,
    name: business.profile.name,
    category: business.profile.category,
    brand_voice: business.profile.brand_voice,
    audience: business.profile.target_audience,
  });
});

// Return products with their matching inventory status.
app.get("/api/business/:id/products", async (req, res) => {
  const business = await findBusinessById(req.params.id);

  if (!business) {
    return res.status(404).json({
      message: "Business not found.",
    });
  }

  const items = business.products.map((product) => {
    const inventoryItem = business.inventory.find(
      (item) => item.product_id === product.product_id
    );

    return {
      id: product.product_id,
      name: product.name,
      price: product.price,
      category: product.category,
      status: inventoryItem?.status || "unknown",
    };
  });

  return res.json({ items });
});

// Return inventory using Roshini's field names.
app.get("/api/business/:id/inventory", async (req, res) => {
  const business = await findBusinessById(req.params.id);

  if (!business) {
    return res.status(404).json({
      message: "Business not found.",
    });
  }

  const items = business.inventory.map((item) => ({
    product_id: item.product_id,
    stock: item.stock_quantity,
    last_restocked: item.last_restocked_at,
  }));

  return res.json({ items });
});

// Return engagement data with product IDs the AI can match.
app.get("/api/business/:id/engagement", async (req, res) => {
  const business = await findBusinessById(req.params.id);

  if (!business) {
    return res.status(404).json({
      message: "Business not found.",
    });
  }

  const items = business.engagement.map((post) => ({
    post_id: post.post_id,
    product_id: post.related_product_ids?.[0] || null,
    type: post.media_type,
    posted_at: post.posted_at,
    likes: post.likes,
    comments: post.comments,
    reach: post.reach,
  }));

  return res.json({ items });
});

// Keep the existing plural profile route for compatibility.
app.get("/api/businesses/:id/profile", async (req, res) => {
  const business = await findBusinessById(req.params.id);

  if (!business) {
    return res.status(404).json({
      success: false,
      message: "Business not found.",
    });
  }

  return res.json({
    business_id: business.businessId,
    ...business.profile,
  });
});

// Keep the existing plural products route.
app.get("/api/businesses/:id/products", async (req, res) => {
  const business = await findBusinessById(req.params.id);

  if (!business) {
    return res.status(404).json({
      success: false,
      message: "Business not found.",
    });
  }

  return res.json({
    products: business.products || [],
  });
});

// Keep the existing plural inventory route.
app.get("/api/businesses/:id/inventory", async (req, res) => {
  const business = await findBusinessById(req.params.id);

  if (!business) {
    return res.status(404).json({
      success: false,
      message: "Business not found.",
    });
  }

  return res.json({
    items: business.inventory || [],
  });
});

// Keep the existing plural engagement route.
app.get("/api/businesses/:id/engagement", async (req, res) => {
  const business = await findBusinessById(req.params.id);

  if (!business) {
    return res.status(404).json({
      success: false,
      message: "Business not found.",
    });
  }

  return res.json({
    posts: business.engagement || [],
  });
});

// Handle requests to routes that do not exist.
app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: "Route not found.",
  });
});

// Handle unexpected server errors.
app.use((err, req, res, next) => {
  console.error("Server error:", err.message);

  if (res.headersSent) {
    return next(err);
  }

  return res.status(500).json({
    success: false,
    message: "Internal server error.",
  });
});

// Start the server only when this file is run directly.
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(
      `MarketMate AI backend running at http://localhost:${PORT}`
    );
  });
}

// Allow automated tests to import the Express app.
module.exports = app;

