## How MarketMate Works

MarketMate is an AI-powered marketing assistant designed to help small businesses make data-informed marketing decisions. It combines business information, product details, inventory levels, and customer engagement data to generate relevant promotional content and actionable recommendations.

### Workflow

**1. Business Data Retrieval — Zetaris**

MarketMate is designed to use Zetaris as its business data layer. The backend retrieves business-specific information, including:

- Business profile, category, target audience, and brand voice
- Product catalog and product details
- Inventory quantities and stock status
- Customer engagement and product-related activity

This information provides the context required to generate recommendations tailored to each business rather than relying solely on generic prompts or hardcoded examples.

**2. Backend Orchestration**

The Node.js backend coordinates requests between the frontend, business data layer, and AI agent. It exposes API endpoints for retrieving business profiles, products, inventory, and engagement data, and passes the relevant business context to the AI workflow.

The backend uses a configurable data-source setting to select the business data provider. In the intended Zetaris-backed workflow, the agent receives data through the backend APIs.

**3. AI Agent and Tool-Based Data Access**

The Python-based AI agent gathers the required business context through tools for retrieving the business profile, products, inventory, and engagement information. These tool calls allow the agent to work with structured business data before producing its recommendations.

The agent is designed to handle incomplete or inconsistent inputs, validate available evidence, and avoid presenting unsupported assumptions as established business facts.

**4. Context-Aware Marketing Recommendations**

Using the retrieved data and the business owner's preferences, MarketMate generates marketing suggestions and promotional content. Recommendations can consider product characteristics, stock availability, engagement patterns, target audience, and the preferred brand voice.

For example, a business that prefers premium, friendly messaging and wants to avoid discounts can receive promotional content that emphasizes product value without automatically proposing price reductions.

**5. Inventory-Aware Decisions**

Inventory information can inform the agent's recommendations. Products with low stock or other inventory concerns can be flagged for the business owner, while product availability can help guide which items are suitable for promotion.

This connects marketing suggestions to operational considerations rather than treating content generation as an isolated task.

**6. Validation and Output**

The generated outputs are checked against the available source data and business preferences. The objective is to produce useful, evidence-based recommendations that remain consistent with the business profile and avoid unsupported product, inventory, or engagement claims.

### Technology Stack

- **Frontend:** Web interface for interacting with business information and marketing recommendations
- **Backend:** Node.js and Express for API routing and orchestration
- **Data Layer:** Zetaris for business data access (integration under verification)
- **AI Agent:** Python-based agent with tool-based data retrieval and recommendation workflows
- **AI Inference:** Meterless Nightshift as the intended primary AI provider, with NVIDIA Nemotron models available through supported inference routes
- **Memory Component:** H-MEM integration for memory-assisted agent workflows

### Integration Status

The project includes a Zetaris client and backend data-access layer intended to retrieve live business data. End-to-end Zetaris connectivity is still being verified; therefore, live retrieval should not be described as fully operational until the SQL API requests succeed.

The AI workflow also includes sample-data and fallback paths for development and testing. Results generated through these paths must be distinguished from recommendations produced using successfully retrieved live Zetaris data.

MarketMate's goal is to connect structured business data, AI-assisted reasoning, and practical marketing decisions in a single workflow for small-business owners.


UI/UX Design

Designed by: Jannatul Ferdous  
Design tool: Figma  
Project: MarketMate — AI Marketing Assistant

Figma Design link: (https://www.figma.com/design/oC7w4mrHhb35fIdXJSgbac)

The design includes 9 screens covering the Overview Dashboard, New Request, Recommendation Results, Processing State, Missing Data State, Error & Retry State, Recommendation History, Business Profile, and Design System & Handoff.

The design includes the updated MarketMate logo and is available as a reference for frontend implementation.


Demo limitations:

* The snapshot and inventory panels are static previews and are not connected to /products.
* The business data source is decided by the backend. The UI does not claim live or Zetaris data.
* Only businessId and the request text are sent. Audience goes in the request text, and type and voice stay in browser storage.
* History is in memory only and resets on refresh.
* The “Demo data” rows in History are fabricated samples.
* API_BASE is http://localhost:3000/.



 Future Improvements

- *Live Zetaris Integration:* Improve reliability when retrieving business profiles, product data, inventory, and engagement metrics from Zetaris.
- *Smarter AI Recommendations:* Improve the Planner, Analyst, Evaluator, and Reporter workflow to generate more accurate, brand-aligned, data-backed marketing recommendations.
- *Platform-Specific Content:* Tailor captions, hashtags, tone, and content formats for Instagram, Facebook, and X.
- *Persistent Brand Memory:* Remember business-owner preferences, brand voice, and promotion policies across sessions using H-MEM.
- *Marketing Calendar:* Let business owners plan, organize, and schedule upcoming social media content.
- *Performance Analytics:* Track engagement and campaign results to help businesses understand which content performs well.
- *Human Review and Editing:* Allow owners to edit, approve, or reject AI-generated recommendations before using them.
- *Improved Error Handling:* Add clearer connection-status messages, retries, and graceful fallbacks when data sources or AI services are unavailable.
- *Multi-Business Support:* Allow users managing multiple businesses to switch between profiles and receive recommendations tailored to each one.

These improvements would help make MarketMate AI more reliable, personalized, and useful for small-business marketing.