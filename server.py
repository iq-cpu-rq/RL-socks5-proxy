"""
Railway SOCKS5 Backend for EdgeTunnel
======================================
All-in-one server: SOCKS5 proxy + HTTP Health Check
Runs as a single process on Railway.
"""

import asyncio
import socket
import struct
import logging
import os
import time
import json
from collections import defaultdict
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

# ============================================================
#  Configuration
# ============================================================
SOCKS_USER = os.getenv("SOCKS_USER", "")
SOCKS_PASS = os.getenv("SOCKS_PASS", "")
SOCKS_PORT = int(os.getenv("SOCKS_PORT", "443"))
HEALTH_PORT = int(os.getenv("PORT", os.getenv("HEALTH_PORT", "8080")))

RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "50"))
CONNECT_TIMEOUT = int(os.getenv("CONNECT_TIMEOUT", "15"))

START_TIME = time.time()
active_connections = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("socks5")

# ============================================================
#  Rate Limiter
# ============================================================
rate_limit_map: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(ip: str) -> bool:
    now = time.time()
    rate_limit_map[ip] = [
        t for t in rate_limit_map[ip]
        if now - t < RATE_LIMIT_WINDOW
    ]
    if len(rate_limit_map[ip]) >= RATE_LIMIT_MAX:
        return False
    rate_limit_map[ip].append(now)
    return True


# ============================================================
#  HTTP Health Check (aiohttp)
# ============================================================
async def health_check(request):
    uptime = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)
    return web.json_response({
        "status": "healthy",
        "service": "socks5-backend",
        "version": "1.0.0",
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "uptime_seconds": uptime,
        "active_socks_connections": active_connections
    })


async def root_handler(request):
    return web.json_response({
        "name": "Railway SOCKS5 Backend",
        "version": "1.0.0",
        "status": "running"
    })


def create_health_app():
    app = web.Application()
    app.router.add_get("/", root_handler)
    app.router.add_get("/healthz", health_check)
    app.router.add_get("/health", health_check)
    return app


# ============================================================
#  SOCKS5 Authentication
# ============================================================
async def authenticate(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
    try:
        header = await asyncio.wait_for(reader.readexactly(2), timeout=10)
        ver, nmethods = header[0], header[1]

        if ver != 0x05:
            return False

        methods = await asyncio.wait_for(reader.readexactly(nmethods), timeout=10)

        if 0x02 not in methods:
            writer.write(b"\x05\xff")
            await writer.drain()
            return False

        writer.write(b"\x05\x02")
        await writer.drain()

        auth_ver = await asyncio.wait_for(reader.readexactly(1), timeout=10)
        if auth_ver[0] != 0x01:
            return False

        ulen = (await asyncio.wait_for(reader.readexactly(1), timeout=10))[0]
        username = (await asyncio.wait_for(reader.readexactly(ulen), timeout=10)).decode(
            "utf-8", errors="ignore"
        )

        plen = (await asyncio.wait_for(reader.readexactly(1), timeout=10))[0]
        password = (await asyncio.wait_for(reader.readexactly(plen), timeout=10)).decode(
            "utf-8", errors="ignore"
        )

        if username == SOCKS_USER and password == SOCKS_PASS:
            writer.write(b"\x01\x00")
            await writer.drain()
            return True
        else:
            writer.write(b"\x01\x01")
            await writer.drain()
            peer = writer.get_extra_info("peername")
            logger.warning(f"Auth FAILED for '{username}' from {peer}")
            return False

    except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionResetError):
        return False


# ============================================================
#  SOCKS5 Connection Handler
# ============================================================
async def relay(src: asyncio.StreamReader, dst: asyncio.StreamWriter):
    try:
        while True:
            data = await src.read(16384)
            if not data:
                break
            dst.write(data)
            await dst.drain()
    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        try:
            if dst.can_write_eof():
                dst.write_eof()
        except (OSError, NotImplementedError):
            pass


async def handle_connect(reader, writer, dest_addr, dest_port):
    global active_connections

    try:
        remote_reader, remote_writer = await asyncio.wait_for(
            asyncio.open_connection(dest_addr, dest_port),
            timeout=CONNECT_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"Timeout → {dest_addr}:{dest_port}")
        reply = b"\x05\x06\x00\x01" + socket.inet_aton("0.0.0.0") + struct.pack("!H", 0)
        writer.write(reply)
        await writer.drain()
        return
    except OSError as e:
        logger.error(f"Cannot connect → {dest_addr}:{dest_port} — {e}")
        reply = b"\x05\x05\x00\x01" + socket.inet_aton("0.0.0.0") + struct.pack("!H", 0)
        writer.write(reply)
        await writer.drain()
        return

    bind_addr = remote_writer.get_extra_info("sockname")
    try:
        bind_ip = socket.inet_aton(bind_addr[0])
        reply = b"\x05\x00\x00\x01" + bind_ip + struct.pack("!H", bind_addr[1])
    except OSError:
        bind_ip = socket.inet_pton(socket.AF_INET6, bind_addr[0])
        reply = b"\x05\x00\x00\x04" + bind_ip + struct.pack("!H", bind_addr[1])

    writer.write(reply)
    await writer.drain()

    active_connections += 1
    logger.info(f"Tunnel → {dest_addr}:{dest_port} (active: {active_connections})")

    await asyncio.gather(
        relay(reader, remote_writer),
        relay(remote_reader, writer),
        return_exceptions=True
    )

    active_connections -= 1

    for w in (writer, remote_writer):
        try:
            w.close()
            await w.wait_closed()
        except Exception:
            pass


# ============================================================
#  SOCKS5 Client Handler
# ============================================================
async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global active_connections
    peer = writer.get_extra_info("peername")
    client_ip = peer[0] if peer else "unknown"

    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limited: {client_ip}")
        writer.close()
        return

    try:
        if not await authenticate(reader, writer):
            writer.close()
            return

        logger.info(f"Authenticated from {client_ip}")

        request_header = await asyncio.wait_for(reader.readexactly(4), timeout=10)
        ver, cmd, _, atyp = request_header

        if ver != 0x05 or cmd != 0x01:
            writer.write(b"\x05\x07\x00\x01" + b"\x00" * 6)
            await writer.drain()
            writer.close()
            return

        if atyp == 0x01:
            raw_addr = await asyncio.wait_for(reader.readexactly(4), timeout=10)
            dest_addr = socket.inet_ntoa(raw_addr)
        elif atyp == 0x03:
            addr_len = (await asyncio.wait_for(reader.readexactly(1), timeout=10))[0]
            dest_addr = (await asyncio.wait_for(reader.readexactly(addr_len), timeout=10)).decode("utf-8")
        elif atyp == 0x04:
            raw_addr = await asyncio.wait_for(reader.readexactly(16), timeout=10)
            dest_addr = socket.inet_ntop(socket.AF_INET6, raw_addr)
        else:
            writer.write(b"\x05\x08\x00\x01" + b"\x00" * 6)
            await writer.drain()
            writer.close()
            return

        dest_port = struct.unpack(
            "!H",
            await asyncio.wait_for(reader.readexactly(2), timeout=10)
        )[0]

        await handle_connect(reader, writer, dest_addr, dest_port)

    except (asyncio.IncompleteReadError, asyncio.TimeoutError,
            ConnectionResetError, BrokenPipeError, OSError):
        pass
    except Exception as e:
        logger.error(f"Error for {client_ip}: {e}", exc_info=False)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


# ============================================================
#  Main — Run Both Servers Together
# ============================================================
async def main():
    if not SOCKS_USER or not SOCKS_PASS:
        logger.critical("SOCKS_USER and SOCKS_PASS MUST be set!")
        raise SystemExit(1)

    if len(SOCKS_PASS) < 16:
        logger.critical("SOCKS_PASS must be at least 16 characters!")
        raise SystemExit(1)

    if SOCKS_USER == "admin" or SOCKS_PASS == "password":
        logger.critical("Change default credentials!")
        raise SystemExit(1)

    # --- Start SOCKS5 Server ---
    socks_server = await asyncio.start_server(
        handle_client,
        "0.0.0.0",
        SOCKS_PORT,
        reuse_address=True
    )
    logger.info(f"SOCKS5 listening on 0.0.0.0:{SOCKS_PORT}")
    logger.info(f"Username: {SOCKS_USER}")
    logger.info(f"Rate limit: {RATE_LIMIT_MAX}/{RATE_LIMIT_WINDOW}s per IP")

    # --- Start HTTP Health Check ---
    health_app = create_health_app()
    runner = web.AppRunner(health_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HEALTH_PORT)
    await site.start()
    logger.info(f"Health check listening on 0.0.0.0:{HEALTH_PORT}")

    # --- Keep Running ---
    logger.info("Both servers running. Ready to accept connections.")
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped.")
