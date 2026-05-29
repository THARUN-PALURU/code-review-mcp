# server.py
# MCP server entry point. Registers tools, routes calls.
# Business logic lives in reviewer.py — keep this file thin.
# support HTTP/SSE transport for team access.
# Uses Streamable HTTP transport — works with modern MCP clients
# like Antigravity standalone app.

import contextlib
import logging
import os
import uvicorn
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp import types
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from reviewer import review_code, review_diff

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

app = Server("code-review-assistant")


# ── Tools ─────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="review_code",
            description=(
                "Review a code snippet. Returns specific comments, "
                "security issues, and optimization tips."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The code to review"
                    }
                },
                "required": ["code"]
            }
        ),
        types.Tool(
            name="review_diff",
            description=(
                "Review a git PR diff. Paste raw `git diff` output. "
                "Returns change-specific feedback."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "diff": {
                        "type": "string",
                        "description": "Raw git diff text"
                    }
                },
                "required": ["diff"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    log.info(f"Tool invoked: {name}")

    if name == "review_code":
        result = review_code(arguments.get("code", ""))
    elif name == "review_diff":
        result = review_diff(arguments.get("diff", ""))
    else:
        result = f"Unknown tool '{name}'. Available: review_code, review_diff"

    return [types.TextContent(type="text", text=result)]


# ── Streamable HTTP Transport ──────────────────────────────────────

# exposes your MCP server over HTTP:
session_manager = StreamableHTTPSessionManager(
    app=app,
    event_store=None,
    json_response=True,
    stateless=True,   #Do not depend on long-lived server memory/session state
)


@contextlib.asynccontextmanager
async def lifespan(starlette_app):
    async with session_manager.run():
        log.info("Code Review MCP Server running at /mcp")
        yield

# passes web requests into the MCP session manager:
async def mcp_asgi_app(scope, receive, send):
    await session_manager.handle_request(scope, receive, send)

# This route is only for browser testing:
async def health(request):
    return JSONResponse({
        "status": "ok",
        "mcp_endpoint": "/mcp"
    })

# This mounts the MCP endpoint:
web_app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/", health, methods=["GET"]),  # '/'      -> health check
        Mount("/mcp", app=mcp_asgi_app),      # '/mcp'   -> MCP endpoint
    ]
)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000")) #Railway gives your app a port through the environment variable:
    uvicorn.run(web_app, host="0.0.0.0", port=port) #Your app must listen on: 0.0.0.0 not localhost, because Railway needs to route external traffic into your container.