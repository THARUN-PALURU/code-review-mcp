# server.py
# MCP server entry point. Registers tools, routes calls.
# Business logic lives in reviewer.py — keep this file thin.
# support HTTP/SSE transport for team access.
# Uses Streamable HTTP transport — works with modern MCP clients
# like Antigravity standalone app.

import contextlib
import logging
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp import types
from starlette.applications import Starlette
from starlette.routing import Mount
import uvicorn

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

session_manager = StreamableHTTPSessionManager(
    app=app,
    event_store=None,
    json_response=False,
    stateless=True,
)


@contextlib.asynccontextmanager
async def lifespan(starlette_app):
    async with session_manager.run():
        log.info("Code Review MCP Server running on http://0.0.0.0:8000/mcp")
        yield


async def mcp_asgi_app(scope, receive, send):
    await session_manager.handle_request(scope, receive, send)


web_app = Starlette(
    lifespan=lifespan,
    routes=[
        Mount("/mcp", app=mcp_asgi_app),
    ]
)


if __name__ == "__main__":
    uvicorn.run(web_app, host="0.0.0.0", port=8000)