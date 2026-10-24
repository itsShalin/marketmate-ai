const fs = require("fs");
const path = require("path");

const filePath = path.join(__dirname, "..", "data", "businesses.json");

const dataset = JSON.parse(fs.readFileSync(filePath, "utf8"));

function getBusinessById(businessId) {
  return (
    dataset.businesses.find(
      (business) => business.businessId === businessId
    ) || null
  );
}

function getAllBusinesses() {
  return dataset.businesses;
}

module.exports = {
  getBusinessById,
  getAllBusinesses,
};