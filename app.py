"""Optional web entry point (Render/Heroku web dyno health check)."""

import asyncio
import os

from aiohttp import web


async def _start():
    app = web.Application()
    app.add_routes([web.get("/", lambda r: web.json_response({"status": "ok"}))])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 5000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server listening on {port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(_start())
