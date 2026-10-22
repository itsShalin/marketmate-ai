
const express = require("express");
const cors = require("cors");

const app = express();
const PORT = 3000;

// Temporary order storage for development.
const orders = [];
let nextOrderId = 1;

// Allow the frontend to send requests to this backend.
app.use(cors());

// Allow the backend to read JSON request bodies.
app.use(express.json());


 // Check whether the backend is running.
 app.get("/api/health", (req, res) => {
  res.status(200).json({
    success: true,
    message: "MarketMate AI backend is running!",
  });
});

// Retrieve all orders.
app.get("/api/orders", (req, res) => {
  res.status(200).json({
    success: true,
    count: orders.length,
    orders: orders,
  });
});


// Receive a marketing request from the frontend.

app.post("/api/agent/run", (req, res) => {
  const { businessId, request } = req.body;
  console.log("REQUEST VALUE:", JSON.stringify(request));


  // Check whether the required information was provided.
  if (
    typeof businessId !== "string" ||
    !businessId.trim() ||
    typeof request !== "string" ||
    request.trim().length === 0
  ) {
    return res.status(400).json({
      success: false,
      message: "businessId and request are required.",
    });
  }

  // The AI service is not connected yet.
  return res.status(501).json({
    success: false,
    message: "AI service integration is not implemented yet.",
  });
});

// Temporarily test the error handler.
app.get("/api/test-error", (req, res, next) => {
  next(new Error("Test error"));
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

  res.status(500).json({
    success: false,
    message: "Internal server error.",
  });
});

// Start the server.
app.listen(PORT, () => {
  console.log(`MarketMate AI server running at http://localhost:${PORT}`);
});
