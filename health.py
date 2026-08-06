"""
Health Check HTTP Server for Railway
=====================================
Railway requires an HTTP endpoint to verify the service is running.
This lightweight aiohttp server provides that endpoint while the
main SOCKS5 server runs on a separate process.
"""

import os
import time
from aiohttp import web

HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8080"))
START_TIME = time.time()


async def health_check(request):
    """Railway health check endpoint."""
    uptime = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)

    return web.json_response({
        "status": "healthy",
        "service": "socks5-backend",
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "uptime_seconds": uptime
    })


async def root(request):
    """Root endpoint — shows service info without exposing details."""
    return web.json_response({
        "name": "Railway SOCKS5 Backend",
        "version": "1.0.0",
        "description": "Secure SOCKS5 proxy for EdgeTunnel",
        "docs": "https://github.com/YOUR_USERNAME/railway-socks5-backend"
    })


async def not_found(request):
    return web.json_response({"error": "Not found"}, status=404)


app = web.Application()
app.router.add_get("/", root)
app.router.add_get("/healthz", health_check)
app.router.add_get("/health", health_check)

if __name__ == "__main__":
    print(f"Health check server starting on port {HEALTH_PORT}")
    web.run_app(app, host="0.0.0.0", port=HEALTH_PORT, print=None)