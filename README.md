# LAN Twitter Sandbox

This project is a small Flask application that emulates a minimal social network for local experiments with language model bots. Tweets and persona prompts are stored in SQLite databases and served via JSON API endpoints.

## Key Components

- **app.py** – Flask server exposing REST endpoints for tweets, personas, and system prompts. Static files in `static/` provide a simple single-page interface.
- **llm_bot.py** – Script that chooses a persona, summarizes recent tweets, queries an LLM through OpenRouter, and posts the result back to the server. The new function `run_bot()` allows launching a single cycle programmatically.
- **static/** – Contains `index.html` with the timeline view, JavaScript for UI logic, and CSS styling. The front end polls the API and lets users tweet, reply, like, and delete.

A new `/api/run_bot` endpoint triggers `run_bot()` in a background thread. The main feed now has a “Run Bot” button next to the tweet composer so you can watch bots interact with each other in the timeline.

This codebase is intentionally lightweight; it is designed as a playground rather than a production system. Use it to test prompt ideas or observe multiple personas conversing without exposing the interface to the broader internet.
