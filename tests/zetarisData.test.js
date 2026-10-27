const test = require("node:test");
const assert = require("node:assert/strict");

const { getTableRecords } = require("../services/zetarisData");

test("getTableRecords rejects an unknown table name", async () => {
  await assert.rejects(
    getTableRecords("unknownTable"),
    /Unknown Zetaris table/
  );
});



  test("getTableRecords queries the approved business table", async () => {
    const originalFetch = global.fetch;
    const originalEnv = {
      ZETARIS_BASE_URL: process.env.ZETARIS_BASE_URL,
      ZETARIS_JWT: process.env.ZETARIS_JWT,
      ZETARIS_ORG_ID: process.env.ZETARIS_ORG_ID,
    };
  
    let requestBody;
  
    process.env.ZETARIS_BASE_URL = "http://localhost:8888";
    process.env.ZETARIS_JWT = "test-token";
    process.env.ZETARIS_ORG_ID = "123";
  
    global.fetch = async (url, options) => {
      requestBody = JSON.parse(options.body);
  
      return {
        ok: true,
        json: async () => ({ records: [{ business_id: "test_business" }] }),
      };
    };
  
    try {
      const records = await getTableRecords("businesses");
  
      assert.match(
        requestBody.select,
        /marketmate_data\.business_profiles_v2/
      );
      assert.equal(records[0].business_id, "test_business");
    } finally {
      global.fetch = originalFetch;
  
      for (const [key, value] of Object.entries(originalEnv)) {
        if (value === undefined) {
          delete process.env[key];
        } else {
          process.env[key] = value;
        }
      }
    }
  });

  for (const tableName of ["products", "engagement", "inventory"]) {
    test(`getTableRecords queries the approved ${tableName} table`, async () => {
      const originalFetch = global.fetch;
      const originalEnv = {
        ZETARIS_BASE_URL: process.env.ZETARIS_BASE_URL,
        ZETARIS_JWT: process.env.ZETARIS_JWT,
        ZETARIS_ORG_ID: process.env.ZETARIS_ORG_ID,
      };
  
      let requestBody;
  
      process.env.ZETARIS_BASE_URL = "http://localhost:8888";
      process.env.ZETARIS_JWT = "test-token";
      process.env.ZETARIS_ORG_ID = "123";
  
      global.fetch = async (url, options) => {
        requestBody = JSON.parse(options.body);
  
        return {
          ok: true,
          json: async () => ({ records: [] }),
        };
      };
  
      try {
        await getTableRecords(tableName);
  
        const expectedTable = {
          products: "marketmate_data\\.products",
          engagement: "marketmate_data\\.engagement",
          inventory: "marketmate_data\\.inventory",
        };
  
        assert.match(requestBody.select, new RegExp(expectedTable[tableName]));
      } finally {
        global.fetch = originalFetch;
  
        for (const [key, value] of Object.entries(originalEnv)) {
          if (value === undefined) {
            delete process.env[key];
          } else {
            process.env[key] = value;
          }
        }
      }
    });
  }