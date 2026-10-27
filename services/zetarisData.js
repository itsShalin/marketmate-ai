
const { query } = require("./zetarisClient");

const TABLES = Object.freeze({
  businesses: "marketmate_data.business_profiles_v2",
  products: "marketmate_data.products",
  inventory: "marketmate_data.inventory",
  engagement: "marketmate_data.engagement",
});

async function getTableRecords(tableName, options = {}) {
  const table = TABLES[tableName];
  if (!table) throw new Error(`Unknown Zetaris table: ${tableName}`);

  let sql = `SELECT * FROM ${table}`;

  if (options.businessId !== undefined) {
    const id = options.businessId;
    if (typeof id !== "string" || !id.trim()) {
      throw new TypeError("businessId must be a non-empty string.");
    }

    sql += ` WHERE business_id = '${id.trim().replace(/'/g, "''")}'`;
  }

  return query(sql, options);
}

function asList(value) {
  if (Array.isArray(value)) return value;
  if (typeof value !== "string" || !value.trim()) return [];

  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) return parsed;
  } catch {
    // The field may contain comma-separated text.
  }

  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

async function getBusinessByIdFromZetaris(businessId) {
  if (typeof businessId !== "string" || !businessId.trim()) {
    throw new TypeError("businessId must be a non-empty string.");
  }

  const id = businessId.trim();

  const [profiles, products, inventory, engagement] = await Promise.all([
    getTableRecords("businesses", { businessId: id }),
    getTableRecords("products", { businessId: id }),
    getTableRecords("inventory", { businessId: id }),
    getTableRecords("engagement", { businessId: id }),
  ]);

  const profile = profiles.find((row) => row.business_id === id);
  if (!profile) return null;

  const brandVoice = [
    profile.brand_voice_tone && `Tone: ${profile.brand_voice_tone}`,
    asList(profile.brand_voice_keywords).length &&
      `Keywords: ${asList(profile.brand_voice_keywords).join(", ")}`,
    asList(profile.brand_voice_avoid).length &&
      `Avoid: ${asList(profile.brand_voice_avoid).join(", ")}`,
  ].filter(Boolean).join("; ");

  return {
    businessId: id,
    profile: {
      name: profile.name,
      category: profile.category,
      description: profile.description,
      brand_voice: brandVoice,
      target_audience: profile.target_audience,
      location: profile.location,
      platforms: asList(profile.platforms),
    },
    products: products.map((item) => ({
      ...item,
      tags: asList(item.tags),
    })),
    inventory: inventory.map((item) => ({
      business_id: item.business_id,
      product_id: item.product_id,
      stock_quantity: Number(item.stock_quantity),
      status: item.status,
      last_restocked_at: item.last_restocked_at,
    })),
    engagement: engagement.map((item) => ({
      ...item,
      related_product_ids: asList(item.related_product_ids),
    })),
  };
}

module.exports = {
  TABLES,
  getTableRecords,
  getBusinessByIdFromZetaris,
};
