## MarketMate AI Agent

MarketMate is an AI-powered marketing assistant designed to help small businesses make data-informed marketing decisions. It combines business information, product details, inventory levels, and customer engagement data to generate relevant promotional content and actionable recommendations.

Built by Team Aevora for the Open Agent Hackathon 2026

## **Features**

* Three request types: social captions, promo campaigns and stock updates.  
* Business-aware drafts: recommendations use the business profile, products and stock status.  
* Evidence and confidence: each draft comes with the reasoning behind it and a confidence level.  
* Safety checks: warnings (for example low stock), data gaps and open questions are shown before the owner publishes.  
* Owner in control: drafts can be edited and copied. Nothing is published automatically.

## 

## **Quick start**

Requires Git, Node.js and Python. Full steps and environment variables are in Detail Setup.

```sh
git clone https://github.com/itsShalin/marketmate-ai.git
cd marketmate-ai
cp .env.example .env                    
 # then fill in your values

# terminal 1: AI agent
cd agent_project && pip install -r requirements.txt && uvicorn main:app --port 8001

# terminal 2: backend
cd backend && npm install && node index.js

# terminal 3: frontend
cd frontend && python -m http.server 5500
```

Open http\://localhost:5500, go to Business profile, enter the Business ID “biz\_cozy\_candles\_001” and click Save profile. Then open a new request and generate a recommendation.


## **How it works**

```
Frontend (HTML/CSS/JS)  ->  Node.js / Express API  ->  Python AI agent
                                    |                         |
                            business data layer        tool-based data access,
                       (Zetaris, or local sample data)   H-MEM, Nemotron models
```

1. Business data: the backend retrieves the business profile, product catalog, inventory and engagement data. Zetaris is the intended data layer. Local sample data is used unless `BUSINESS_DATA_SOURCE=zetaris` is set.   
2. Orchestration: the Node.js backend validates the request, gathers business context and forwards it to the agent.  
3. Agent: the Python agent uses tools to fetch business data, then runs planner, analyst and evaluator steps. It is designed to handle incomplete inputs and not present unsupported assumptions as business facts.  
4. Recommendations: drafts consider product characteristics, stock availability, engagement, audience and brand voice. For example, a business that wants to avoid discounts can get promotional copy that highlights product value without proposing price cuts.  
5. Inventory awareness: low-stock products are flagged for the owner, and availability guides which items are suitable for promotion.  
6. Validation: outputs are checked against the available data and business preferences to avoid unsupported product, inventory or engagement claims.

Stack: plain HTML/CSS/JS frontend · Node.js \+ Express backend · Python \+ FastAPI agent · Zetaris data layer (under verification) · Meterless Nightshift as the intended primary AI provider, with NVIDIA Nemotron models available through supported routes · H-MEM memory component.

## Detailed setup

### 1\. Prerequisites

* Git  
* Node.js 18 or newer 
* Python 3.10 or newer 
* Credentials for the services in [Dependencies](https://claude.ai/chat/02d0cfb0-a7e1-42fd-be93-d798a815f676#dependencies), if you are not running on sample data

### 

### 2\. Clone

```sh
git clone https://github.com/itsShalin/marketmate-ai.git
cd marketmate-ai
```

### 

### 3\. Environment variables

```sh
cp .env.example .env        # macOS / Linux
copy .env.example .env      # Windows
```

Fill in your own values. Never commit real keys.

| Variable | Purpose | Example |
| ----- | ----- | ----- |
| `BUSINESS_DATA_SOURCE` | Business data provider. Local sample data is used unless this is `zetaris`. | `local` |
| `PORT` | Express API port | `3000` |
| `AGENT_URL` | Where Express reaches the Python agent | `http://localhost:<AGENT_PORT>` |
| `NVIDIA_API_KEY` | Nemotron model access | `your-key-here` |
| `METERLESS_*` | Meterless Nightshift settings | `TODO` |
| `ZETARIS_*` | Zetaris connection settings (only if `BUSINESS_DATA_SOURCE=zetaris`) | `TODO` |

\<\!-- TODO (Roshni): replace with the real variable names from .env.example. →

### 4\. Start the Python agent

```sh
cd agent_project
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --port <AGENT_PORT>
```

### 

### 5\. Start the Node.js backend

In a second terminal:

```sh
cd backend
npm install
node index.js
```

Check it is running:

```sh
curl http://localhost:3000/api/health
# {"success":true,"message":"MarketMate AI backend is running!"}
```

### 

### 6\. Start the frontend

In a third terminal:

```sh
cd frontend
python -m http.server 5500
```

Open http\://localhost:5500. The header pill should read Backend connected. To point the frontend at a different backend, change `API_BASE` at the top of `frontend/script.js`.


## Usage

### Through the frontend

1. Open Business profile, enter the Business ID `biz_cozy_candles_001` and click Save profile. The business name is filled in from the backend.  
2. Open a new request and choose a goal.  
3. Enter a request (samples below) and click Generate recommendation.  
4. Review the draft, the “Why this recommendation?” panel and the Check before publishing warnings. Copy or edit the draft.

### 

### Sample inputs

Business ID: `biz_cozy_candles_001` (Cozy Candle Co.)

| Goal | Sample request |
| ----- | ----- |
| Social caption | `Create an Instagram caption for Cozy Candle Co. autumn collection.` |
| Promo campaign | `Create a promotional campaign for our candles this weekend.` |
| Stock update | `Generate a stock update post for our freshly restocked bestsellers.` |

An optional target audience entered in the UI is appended to the request as `(Audience: ...)`.

### Through the API

`POST /api/agent/run` with `{ "businessId": "...", "request": "..." }`. Both fields must be non-empty strings.

```sh
curl -X POST http://localhost:3000/api/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "businessId": "biz_cozy_candles_001",
    "request": "Create a promotional campaign for our candles this weekend."
  }'
```

PowerShell:

```
$body = @{
  businessId = "biz_cozy_candles_001"
  request    = "Create a promotional campaign for our candles this weekend."
} | ConvertTo-Json

$response = Invoke-RestMethod -Method Post -Uri http://localhost:3000/api/agent/run `
  -ContentType "application/json" -Body $body

$response.recommendations | Select-Object type, draft, confidence, rationale, warnings | Format-List
```

A real request can take a while because the agent runs several steps. The backend allows the AI service up to 200 seconds.

Other endpoints:

```sh
curl http://localhost:3000/api/health
curl http://localhost:3000/api/business/biz_cozy_candles_001
curl http://localhost:3000/api/business/biz_cozy_candles_001/products
```

### 

### 

### Response fields

| Field | Meaning |
| ----- | ----- |
| `recommendations[]` | One or more drafts. Each has `type`, `draft`, `confidence`, `rationale` / `evidence`, and may have its own `warnings` (for example "Low stock; confirm availability before promoting."). |
| `warnings` | Top-level warnings |
| `data_gaps` | Business data the agent could not use |
| `questions_for_owner` | Questions that would improve the result |
| `limitations` | Known limits of the answer |
| `mock` | `true` for sample responses |

The backend returns the agent's response unchanged, so the shape of recommendation-level fields is not a fixed schema. The frontend renders them defensively.

## Dependencies

| Dependency | Used for |
| ----- | ----- |
| Node.js \+ Express | Backend API (`/api/health`, `/api/business/:id`, `/api/business/:id/products`, `/api/agent/run`) |
| Python \+ FastAPI | Agent service |
| NVIDIA Nemotron | Models routed per agent step. The logs show `nvidia/nemotron-3-ultra-550b-a55b` (planner, evaluator) and `nvidia/nemotron-3.5-super-vl-120b-a12b` (analyst). |
| H-MEM | Memory step in the agent workflow |
| Browser | Frontend. Inter font is loaded from Google Fonts, with a system-font fallback. |

### 

### Zetaris


* Role: business data layer for profile, products, inventory and engagement data.  
* Status: client and data-access layer exist, but end-to-end connectivity is still being verified. The backend uses local sample data unless `BUSINESS_DATA_SOURCE=zetaris` is set.  
* Setup: `TODO: endpoint, credentials, how to switch it on`

### Meterless Nightshift


* Role: intended primary AI inference provider, with NVIDIA Nemotron models available through supported inference routes.  
* Where it sits: `TODO: which agent steps go through it`  
* Setup: `TODO: account, API key, install or config steps`



## Integration status

The project includes a Zetaris client and backend data-access layer intended to retrieve live business data. End-to-end Zetaris connectivity is still being verified, so live retrieval should not be described as fully operational until the SQL API requests succeed.

The AI workflow also includes sample-data and fallback paths for development and testing. Results generated through these paths must be distinguished from recommendations produced using successfully retrieved live Zetaris data.

## Demo limitations

* The snapshot and inventory panels are static previews and are not connected to `/products`.  
* The business data source is decided by the backend. The UI does not claim live or Zetaris data.  
* Only `businessId` and the request text are sent. Audience goes in the request text, and business type and brand voice stay in browser storage.  
* History is in memory only and resets on refresh.  
* The "Demo data" rows in History are fabricated samples.  
* `API_BASE` is `http://localhost:3000`.  
* Drafts are suggestions. Verify prices, stock and offer terms before publishing.

## 

## Future improvements

* Live Zetaris integration: more reliable retrieval of business profiles, products, inventory and engagement metrics.  
* Smarter AI recommendations: improve the Planner, Analyst, Evaluator and Reporter workflow for more accurate, brand-aligned, data-backed output.  
* Platform-specific content: tailor captions, hashtags, tone and formats for Instagram, Facebook and X.  
* Persistent brand memory: remember owner preferences, brand voice and promotion policies across sessions using H-MEM.  
* Marketing calendar: plan, organize and schedule upcoming social content.  
* Performance analytics: track engagement and campaign results.  
* Human review and editing: let owners edit, approve or reject recommendations before use.  
* Improved error handling: clearer connection status, retries and graceful fallbacks.  
* Multi-business support: switch between several business profiles.


## UI/UX design

Designed by Jannatul Ferdous in Figma: [MarketMate design file](https://www.figma.com/design/oC7w4mrHhb35fIdXJSgbac).

The design has 9 screens: Overview Dashboard, New Request, Recommendation Results, Processing State, Missing Data State, Error & Retry State, Recommendation History, Business Profile, and Design System & Handoff. It includes the updated MarketMate logo and serves as the reference for the frontend implementation.

## 

## Team Aevora: 

Shalin (Lead) · Jannatul (UI/UX) · Varshini (Frontend) · Roshni (Backend & AI)




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