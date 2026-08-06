"""
Railway SOCKS5 Backend for EdgeTunnel
======================================
A secure, authenticated SOCKS5 proxy server designed to run on Railway
and be used as a fixed-IP backend for cmliu/edgetunnel Cloudflare Worker.

Features:
- Full SOCKS5 protocol with Username/Password authentication
- Async I/O with asyncio for high concurrency
- Built-in rate limiting per IP
- IPv4, IPv6, and Domain name support
- Designed for Cloudflare Workers compatibility (port 443)
"""

import asyncio
import socket
import struct
import logging
import os
import time
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

# ============================================================
#  Configuration
# ============================================================
SOCKS_USER = os.getenv("SOCKS_USER", "")
SOCKS_PASS = os.getenv("SOCKS_PASS", "")
SOCKS_PORT = int(os.getenv("SOCKS_PORT", "443"))

# Rate Limiting
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "50"))

# Connection timeout
CONNECT_TIMEOUT = int(os.getenv("CONNECT_TIMEOUT", "15"))

# Logging
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
    """Returns True if connection is allowed, False if rate limited."""
    now = time.time()
    # Clean old entries
    rate_limit_map[ip] = [
        t for t in rate_limit_map[ip]
        if now - t < RATE_LIMIT_WINDOW
    ]
    if len(rate_limit_map[ip]) >= RATE_LIMIT_MAX:
        return False
    rate_limit_map[ip].append(now)
    return True


# ============================================================
#  SOCKS5 Authentication
# ============================================================
async def authenticate(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
    """
    Perform SOCKS5 Username/Password authentication (RFC 1929).
    Returns True if authenticated successfully.
    """
    try:
        # --- Step 1: Method Selection ---
        header = await asyncio.wait_for(reader.readexactly(2), timeout=10)
        ver, nmethods = header[0], header[1]

        if ver != 0x05:
            logger.debug(f"Invalid SOCKS version: {ver}")
            return False

        methods = await asyncio.wait_for(reader.readexactly(nmethods), timeout=10)

        # We only accept method 0x02 (Username/Password)
        if 0x02 not in methods:
            writer.write(b"\x05\xff")  # No acceptable methods
            await writer.drain()
            return False

        # Tell client we chose method 0x02
        writer.write(b"\x05\x02")
        await writer.drain()

        # --- Step 2: Credentials ---
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

        # --- Step 3: Verify ---
        if username == SOCKS_USER and password == SOCKS_PASS:
            writer.write(b"\x01\x00")  # Success
            await writer.drain()
            return True
        else:
            writer.write(b"\x01\x01")  # Failure
            await writer.drain()
            peer = writer.get_extra_info("peername")
            logger.warning(f"Auth FAILED for user '{username}' from {peer}")
            return False

    except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionResetError):
        return False


# ============================================================
#  Connection Handler
# ============================================================
async def relay(src: asyncio.StreamReader, dst: asyncio.StreamWriter):
    """Relay data from src to dst until connection closes."""
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


async def handle_connect(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    dest_addr: str,
    dest_port: int
):
    """Connect to destination and establish bidirectional tunnel."""
    try:
        remote_reader, remote_writer = await asyncio.wait_for(
            asyncio.open_connection(dest_addr, dest_port),
            timeout=CONNECT_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"Timeout connecting to {dest_addr}:{dest_port}")
        reply = b"\x05\x06\x00\x01" + socket.inet_aton("0.0.0.0") + struct.pack("!H", 0)
        writer.write(reply)
        await writer.drain()
        return
    except OSError as e:
        logger.error(f"Cannot connect to {dest_addr}:{dest_port} — {e}")
        reply = b"\x05\x05\x00\x01" + socket.inet_aton("0.0.0.0") + struct.pack("!H", 0)
        writer.write(reply)
        await writer.drain()
        return

    # Send success reply with bound address
    bind_addr = remote_writer.get_extra_info("sockname")
    try:
        bind_ip = socket.inet_aton(bind_addr[0])
        reply = b"\x05\x00\x00\x01" + bind_ip + struct.pack("!H", bind_addr[1])
    except OSError:
        # IPv6 fallback
        bind_ip = socket.inet_pton(socket.AF_INET6, bind_addr[0])
        reply = b"\x05\x00\x00\x04" + bind_ip + struct.pack("!H", bind_addr[1])

    writer.write(reply)
    await writer.drain()

    logger.info(f"Tunnel → {dest_addr}:{dest_port}")

    # Bidirectional relay
    await asyncio.gather(
        relay(reader, remote_writer),
        relay(remote_reader, writer),
        return_exceptions=True
    )

    # Cleanup
    for w in (writer, remote_writer):
        try:
            w.close()
            await w.wait_closed()
        except Exception:
            pass


# ============================================================
#  Client Handler
# ============================================================
async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Main handler for each incoming SOCKS5 connection."""
    peer = writer.get_extra_info("peername")
    client_ip = peer[0] if peer else "unknown"

    # --- Rate Limit Check ---
    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limited: {client_ip}")
        writer.close()
        return

    try:
        # --- Authentication ---
        if not await authenticate(reader, writer):
            writer.close()
            return

        logger.info(f"Authenticated connection from {client_ip}")

        # --- Read CONNECT Request ---
        request_header = await asyncio.wait_for(reader.readexactly(4), timeout=10)
        ver, cmd, _, atyp = request_header

        # Only CONNECT (0x01) is supported
        if ver != 0x05 or cmd != 0x01:
            # Reply: Command not supported
            writer.write(b"\x05\x07\x00\x01" + b"\x00" * 6)
            await writer.drain()
            writer.close()
            return

        # --- Parse Destination Address ---
        if atyp == 0x01:  # IPv4
            raw_addr = await asyncio.wait_for(reader.readexactly(4), timeout=10)
            dest_addr = socket.inet_ntoa(raw_addr)
        elif atyp == 0x03:  # Domain Name
            addr_len = (await asyncio.wait_for(reader.readexactly(1), timeout=10))[0]
            dest_addr = (await asyncio.wait_for(reader.readexactly(addr_len), timeout=10)).decode("utf-8")
        elif atyp == 0x04:  # IPv6
            raw_addr = await asyncio.wait_for(reader.readexactly(16), timeout=10)
            dest_addr = socket.inet_ntop(socket.AF_INET6, raw_addr)
        else:
            # Address type not supported
            writer.write(b"\x05\x08\x00\x01" + b"\x00" * 6)
            await writer.drain()
            writer.close()
            return

        # --- Parse Destination Port ---
        dest_port = struct.unpack(
            "!H",
            await asyncio.wait_for(reader.readexactly(2), timeout=10)
        )[0]

        # --- Establish Tunnel ---
        await handle_connect(reader, writer, dest_addr, dest_port)

    except (asyncio.IncompleteReadError, asyncio.TimeoutError,
            ConnectionResetError, BrokenPipeError, OSError):
        pass
    except Exception as e:
        logger.error(f"Unexpected error for {client_ip}: {e}", exc_info=False)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


# ============================================================
#  Main Entry Point
# ============================================================
async def main():
    # Validate configuration
    if not SOCKS_USER or not SOCKS_PASS:
        logger.critical("SOCKS_USER and SOCKS_PASS environment variables MUST be set!")
        raise SystemExit(1)

    if len(SOCKS_PASS) < 16:
        logger.critical("SOCKS_PASS must be at least 16 characters long!")
        raise SystemExit(1)

    if SOCKS_USER == "admin" or SOCKS_PASS == "password":
        logger.critical("Please change default credentials! This is insecure.")
        raise SystemExit(1)

    server = await asyncio.start_server(
        handle_client,
        "0.0.0.0",
        SOCKS_PORT,
        reuse_address=True,
        reuse_port=True
    )

    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    logger.info(f"SOCKS5 Auth Server listening on {addrs}")
    logger.info(f"Username: {SOCKS_USER}")
    logger.info(f"Rate limit: {RATE_LIMIT_MAX} connections / {RATE_LIMIT_WINDOW}s per IP")
    logger.info(f"Connect timeout: {CONNECT_TIMEOUT}s")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")