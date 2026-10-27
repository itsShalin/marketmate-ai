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
