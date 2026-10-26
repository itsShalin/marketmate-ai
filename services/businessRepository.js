const { getBusinessById } = require("./businessData");
const { getBusinessByIdFromZetaris } = require("./zetarisData");

async function findBusinessById(businessId) {
  if (process.env.BUSINESS_DATA_SOURCE !== "zetaris") {
    return getBusinessById(businessId);
  }

  return getBusinessByIdFromZetaris(businessId);
}

module.exports = { findBusinessById };
