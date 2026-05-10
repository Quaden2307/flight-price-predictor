# Week of May 3-10, 2026

This week the data collection pipeline went live. Started the week with "I have an idea about scraping flight data" and ended with a daily automated job that runs without me touching it.

May 3-7 was figuring out the API. Originally planned to use Amadeus but found out their self-service portal is being decommissioned in July, so I switched to TravelPayouts/Aviasales. Got the token, ran some test queries in the browser, and started building the SQLite schema in parallel with my Phase 1 EDA work. The reasoning was that as the initial model is being built, data will be storing every day for future use.

May 9 was building collect.py. Started with one-way collection across 3 test routes, got it working end-to-end, then realized round-trip is a totally different price object on legacy carriers — RT prices are typically 30-50% cheaper than 2 one-ways because of fare class rules and Saturday-night-stay incentives. So I dropped one-way collection and switched to round-trip-only.

The biggest surprise came on May 9-10: the API caps round-trip queries at a 30-day gap between depart and return. Found this out after designing a 5-offset strategy that was supposed to cover internship-length trips (4-month round trips). Instead of fighting the API, I narrowed scope to 0-60 day trips (vacations and short business trips) and shifted the product positioning toward international vacation travel, which honestly fits the route mix better. Long-trip coverage is on hold until either a free API supports it or this project has paying users to justify a paid one.

The route list ended up at 230 routes — Toronto-heavy because that's where I'll launch first (Toronto/Vancouver friends, LinkedIn, school networks), plus US tech hubs, European cities for vacation coverage, East Asia (Japan, China, Korea), Latin America, and a small batch of intra-Asia routes for multi-country trip legs. Removed Middle East entirely; was originally there for Tel Aviv business travel but doesn't fit the vacation pivot.

By end of week the daily job was running through launchd. It fires collect.py every morning at 6 AM and writes ~4,000 round-trip offers into flights.db. Two consecutive runs produced 4,350 and 4,358 offers with zero failures, so the pipeline is stable. From here it's mostly hands-off — let data accumulate for ~30 days, build feature engineering and the train-test split in parallel, and start training once there's enough time-series depth.

Things to do next week: populate the airports reference table from OurAirports CSV (need it for distance and region features in the eventual model), keep working on Phase 1 EDA, and start sketching features.py for Phase 2.
