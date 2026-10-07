# 0009 — The web page is React

Status: accepted · 2026-10-07

The web Channel is a Vite + React + TypeScript app in a top-level `web/` folder (its own toolchain justifies the folder; `src/stepout/` stays organised by module), built to `web/dist` and served by the Python process over aiohttp, speaking WebSocket through the same Channel interface as Telegram. In V0 it is localhost / home Wi-Fi only, with no sign-in. A hosted site where people sign in and run workflows is the V1 goal: authentication will come from a provider rather than being hand-written, and Vite SPA versus Next.js is decided then. Rejected: a plain HTML page (it would be thrown away), and FastAPI + uvicorn (aiohttp is already installed through aiogram).
