
const test = require("node:test");
const assert = require("node:assert/strict");

const {
  getBusinessById,
  getAllBusinesses,
} = require("../services/businessData");

test("getBusinessById returns the matching business", () => {
  const business = getBusinessById("biz_cozy_candles_001");

  assert.ok(business);
  assert.equal(business.businessId, "biz_cozy_candles_001");
});

test("getBusinessById returns null for an unknown business", () => {
  const business = getBusinessById("fake_business_999");

  assert.equal(business, null);
});

test("getAllBusinesses returns an array", () => {
  const businesses = getAllBusinesses();

  assert.ok(Array.isArray(businesses));
  assert.ok(businesses.length > 0);
});

test("every business has an ID and a profile", () => {
  const businesses = getAllBusinesses();

  for (const business of businesses) {
    assert.equal(typeof business.businessId, "string");
    assert.ok(business.profile);
  }
});
