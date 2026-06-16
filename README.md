# Code Review Assistant — MCP Server

> **What this is:** An AI tool that reviews your code for bugs, security issues, and improvements. You paste code, it gives feedback. It works inside your AI assistant (like Claude or Antigravity) as a connected tool.

> **Who built it:** [Tharun Paluru](https://github.com/THARUN-PALURU) as a learning project to understand Model Context Protocol (MCP) — the emerging standard for connecting AI models to external tools.

[![Live Server](https://img.shields.io/badge/Live%20Server-Railway-violet)](https://web-production-cc55f.up.railway.app/)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-1.27.1-purple)](https://github.com/modelcontextprotocol/python-sdk)
[![Model](https://img.shields.io/badge/Model-Llama%203.3%2070B-orange)](https://groq.com)

---

## Quick Start — Use It Right Now (No Setup Needed)

Add this to your AI client's config file and restart:

```json
{
  "mcpServers": {
    "code-review": {
      "serverUrl": "https://web-production-cc55f.up.railway.app/mcp/"
    }
  }
}
```

**Where is the config file?**

| Your AI Client | Config File Location |
|---|---|
| Antigravity (standalone app) | `C:\Users\YourName\.gemini\config\mcp_config.json` |
| Antigravity (VS Code extension) | `C:\Users\YourName\.gemini\antigravity\mcp_config.json` |
| Claude Desktop (Windows) | `C:\Users\YourName\AppData\Roaming\Claude\claude_desktop_config.json` |
| Claude Desktop (Mac) | `~/Library/Application Support/Claude/claude_desktop_config.json` |

After restarting, you'll see **"code-review ● 2 tools enabled"** — then ask your AI to review code!

---

## What Does It Actually Do?

It gives you the same feedback a senior developer would give — without waiting for one.

**Tool 1: `review_code`** — Paste any code snippet

```python
# You paste this:
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    return db.execute(query)

# You get back:
## Code Review Comments
# - user_id is not validated before being used in query (line 2)

## Security Suggestions
# CRITICAL: SQL injection vulnerability — attacker can manipulate the query
# Fix: Use parameterized queries:
#   db.execute("SELECT * FROM users WHERE id = %s", (user_id,))

## Optimization Tips  
# - Add type hints: def get_user(user_id: int) -> dict
# - Wrap db.execute() in try/except to handle connection failures
```

**Tool 2: `review_diff`** — Paste a Git diff (for PR reviews)

```bash
# Get a diff with:
git diff HEAD~1

# Paste the output and get feedback on what changed
```

---

## Understanding MCP (The "Why" Behind This Project)

Before diving into code, here's the concept that makes this work:

```
THE OLD WAY (without MCP):
──────────────────────────
Your code → Claude API → Response
Your code → GPT API   → Response  
Your code → Gemini API → Response
= Different code for every AI

THE MCP WAY:
──────────────────────────
Your Tool (MCP Server)
    ↑
Any AI Client connects to it
= One tool, works everywhere
```

**MCP (Model Context Protocol)** is like a USB standard for AI tools. Just as any USB device works with any USB port, any MCP server works with any MCP client. Anthropic created this standard in 2024 and it's rapidly becoming the industry norm.

**Two ways MCP servers communicate:**

| Transport | How it works | Used when |
|---|---|---|
| `stdio` | AI client launches your server as a subprocess | Local use only — your machine |
| `Streamable HTTP` | Your server runs independently, client connects via URL | Shared/deployed — anyone can use |

This project uses **Streamable HTTP** so anyone with the URL can connect.

---

## Build It From Scratch — Complete Guide

Even if you've never built an API or used AI tools before, follow these steps exactly.

### What You Need Before Starting

1. **Python 3.10+** — Download from [python.org](https://python.org/downloads)
   - Windows: Check ✅ "Add Python to PATH" during install
   - Mac: `brew install python@3.12`
   
2. **VS Code** — Download from [code.visualstudio.com](https://code.visualstudio.com)

3. **Git** — Download from [git-scm.com](https://git-scm.com/downloads)

4. **Free Groq API Key** — Sign up at [console.groq.com](https://console.groq.com) (no credit card)

### Step 1 — Project Setup

```bash
# Create project folder
mkdir code-review-mcp
cd code-review-mcp

# Create Python virtual environment (isolated package space)
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# You should see (venv) in your terminal prompt now

# Install required packages
pip install mcp groq python-dotenv starlette uvicorn
```

### Step 2 — Store Your API Key

Create a file named `.env` (just that, no other extension) in your project folder:

```
GROQ_API_KEY=gsk_your_actual_key_here
```

**Why .env?** Never put API keys directly in code. If you push code to GitHub, the key gets exposed. The `.env` file stays only on your machine.

### Step 3 — Create .gitignore

Create `.gitignore` file:

```
venv/
.env
__pycache__/
*.pyc
.DS_Store
```

This tells Git to never upload these files.

### Step 4 — Create prompts.py

This file holds the instructions we send to the AI. Keep prompts separate from logic so you can improve them without touching code.

```python
# prompts.py
# Instructions sent to Llama 3.3 for each type of review.
# Edit these to improve review quality without touching other files.

CODE_REVIEW = """You are a senior engineer doing a thorough but practical code review.

Review the code below and return feedback in this exact format:

## Code Review Comments
- Specific issues, with line numbers where possible
- Flag things that will actually cause bugs, not just style nitpicks

## Security Suggestions
- Real vulnerabilities only (SQL injection, hardcoded secrets, unsafe evals)
- Skip generic advice unless there's a concrete threat

## Optimization Tips
- Performance wins, readability fixes, missing type hints if they help
- Keep it actionable

If something looks genuinely fine, say so. Don't pad the review.

CODE:
{code}
"""

DIFF_REVIEW = """You are reviewing a pull request as a senior engineer.

Focus on what actually changed. Return feedback in this format:

## Code Review Comments
- Are the changes correct and complete?
- Any edge cases the author missed?

## Security Suggestions
- Any new attack surface introduced by these changes?

## Optimization Tips
- Better approaches to what was changed?

Be concise. The author knows the codebase.

DIFF:
{diff}
"""
```

### Step 5 — Create reviewer.py

This file handles all AI communication. The MCP server calls functions here and never talks to the AI directly.

```python
# reviewer.py
# Calls Groq API and returns review text.
# Keep all LLM logic here — server.py shouldn't know which model we use.

import os
import logging
from groq import Groq
from dotenv import load_dotenv
from prompts import CODE_REVIEW, DIFF_REVIEW

load_dotenv()  # Reads your .env file

log = logging.getLogger(__name__)

_client = None  # Created once, reused — saves connection overhead


def _get_client():
    """Get or create Groq client. Only connects when first needed."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set in .env")
        _client = Groq(api_key=api_key)
    return _client


MODEL = "llama-3.3-70b-versatile"  # Best free model on Groq as of 2025


def review_code(code: str) -> str:
    """Review a code snippet. Returns review as plain text."""
    if not code or not code.strip():
        return "No code provided."
    if len(code.strip()) < 10:
        return "Code too short to review meaningfully."

    log.info(f"Reviewing code snippet ({len(code)} chars)")
    return _call_llm(CODE_REVIEW.format(code=code))


def review_diff(diff: str) -> str:
    """Review a git PR diff. Returns review as plain text."""
    if not diff or not diff.strip():
        return "No diff provided."
    if not diff.startswith("diff --git") and "@@" not in diff:
        return "Input doesn't look like a valid git diff. Paste raw `git diff` output."

    log.info(f"Reviewing diff ({len(diff)} chars)")
    return _call_llm(DIFF_REVIEW.format(diff=diff))


def _call_llm(prompt: str) -> str:
    """Send prompt to Groq, return response text."""
    try:
        resp = _get_client().chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,   # Low = consistent output (good for code review)
            max_tokens=1024,   # Enough for detailed review
        )
        return resp.choices[0].message.content

    except RuntimeError as e:
        return f"Config error: {e}"
    except Exception as e:
        log.error(f"Groq call failed: {e}")
        return f"Review failed: {e}"
```

### Step 6 — Create server.py

This is the MCP server. It registers your tools and handles the protocol.

```python
# server.py
# MCP server entry point. Registers tools, routes calls.
# Business logic lives in reviewer.py — keep this file thin.

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

# The core MCP server object
app = Server("code-review-assistant")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """MCP clients call this to discover what tools exist (like a menu)."""
    return [
        types.Tool(
            name="review_code",
            description="Review a code snippet. Returns comments, security issues, and optimization tips.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The code to review"}
                },
                "required": ["code"]
            }
        ),
        types.Tool(
            name="review_diff",
            description="Review a git PR diff. Paste raw `git diff` output. Returns change-specific feedback.",
            inputSchema={
                "type": "object",
                "properties": {
                    "diff": {"type": "string", "description": "Raw git diff text"}
                },
                "required": ["diff"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Called when client invokes a tool. Routes to the right function."""
    log.info(f"Tool invoked: {name}")

    if name == "review_code":
        result = review_code(arguments.get("code", ""))
    elif name == "review_diff":
        result = review_diff(arguments.get("diff", ""))
    else:
        result = f"Unknown tool '{name}'. Available: review_code, review_diff"

    return [types.TextContent(type="text", text=result)]


# Streamable HTTP transport (MCP 2025 spec — works with modern clients)
session_manager = StreamableHTTPSessionManager(
    app=app,
    event_store=None,
    json_response=True,   # JSON format, not SSE stream
    stateless=True,       # No session state — each request independent
)


@contextlib.asynccontextmanager
async def lifespan(starlette_app):
    """Runs when server starts and stops."""
    async with session_manager.run():
        log.info("Code Review MCP Server running at /mcp")
        yield


async def mcp_asgi_app(scope, receive, send):
    """Raw ASGI handler — passes requests to MCP session manager."""
    await session_manager.handle_request(scope, receive, send)


async def health(request):
    """Simple health check — open in browser to verify server is live."""
    return JSONResponse({"status": "ok", "mcp_endpoint": "/mcp"})


web_app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/", health, methods=["GET"]),      # Health check
        Mount("/mcp", app=mcp_asgi_app),           # MCP endpoint
    ]
)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))    # Railway sets PORT, local uses 8000
    uvicorn.run(web_app, host="0.0.0.0", port=port)
```

### Step 7 — Create Procfile (for deployment)

```
web: uvicorn server:web_app --host 0.0.0.0 --port $PORT
```

### Step 8 — Test Locally

```bash
# Test the review logic directly (no MCP client needed)
python -c "
from reviewer import review_code
print(review_code('def divide(a, b): return a / b'))
"
# Expected: Review mentioning ZeroDivisionError

# Start the server
python server.py
# Expected: "Code Review MCP Server running at /mcp"
```

Open browser → `http://localhost:8000/` → should see `{"status":"ok"}`

### Step 9 — Connect Your AI Client

Update your `mcp_config.json` (see Quick Start section above) with:
```json
{"mcpServers": {"code-review": {"serverUrl": "http://localhost:8000/mcp/"}}}
```

Restart your client → green dot → test a code review!

### Step 10 — Deploy to Railway

```bash
# 1. Generate clean requirements
pip freeze | Out-File -FilePath requirements.txt -Encoding ascii  # Windows
# OR
pip freeze > requirements.txt  # Mac/Linux

# 2. Push to GitHub
git init
git add .
git commit -m "Code Review MCP Server"
git remote add origin https://github.com/yourusername/code-review-mcp.git
git push -u origin main

# 3. Go to railway.app → New Project → Deploy from GitHub
# 4. Add GROQ_API_KEY in Variables tab
# 5. Get your public URL from Settings → Networking
```

---

## Project Structure

```
code-review-mcp/
├── server.py          ← MCP server (tool registration, HTTP routing)
├── reviewer.py        ← Business logic (Groq API calls, error handling)
├── prompts.py         ← Prompt templates (edit to improve review quality)
├── Procfile           ← Railway deployment command
├── requirements.txt   ← Python dependencies
├── .env               ← API keys (NEVER commit this)
└── .gitignore         ← Excludes .env, venv from git
```

**Rule of thumb:**
- Want better reviews? Edit `prompts.py`
- Want to add a new tool? Edit `server.py` + `reviewer.py`
- Want to change the AI model? Edit one line in `reviewer.py`

---

## How It All Connects (Flow Diagram)

```
1. You type in Antigravity:
   "Use review_code to review: def add(a,b): return a+b"
          │
          ▼
2. Antigravity's AI decides to call your tool
          │
          ▼
3. HTTP POST to /mcp/ with:
   {"name": "review_code", "arguments": {"code": "def add..."}}
          │
          ▼
4. server.py receives → call_tool("review_code", {...})
          │
          ▼
5. reviewer.py builds prompt using CODE_REVIEW template
          │
          ▼
6. Groq API sends to Llama 3.3 → waits ~2-3 seconds
          │
          ▼
7. Review text returned → server.py wraps in TextContent
          │
          ▼
8. Antigravity displays the review
```

---

## Troubleshooting

| Error | What it means | Fix |
|---|---|---|
| `No module named 'mcp'` | venv not active | Run `venv\Scripts\activate` |
| `GROQ_API_KEY not set` | .env not loading | Check no spaces around `=` in .env |
| `401 Authentication Failed` | Wrong API key | Get new key from console.groq.com |
| `model_decommissioned` | Groq retired model | Change `MODEL` in reviewer.py to `llama-3.3-70b-versatile` |
| `Failed to load MCP servers` | JSON encoding issue | Save config file as UTF-8 (not UTF-8 with BOM) |
| `Method Not Allowed` | Wrong MCP transport | Use Streamable HTTP, not SSE |
| Green dot missing | Server not running | Run `python server.py` first |

---

## Tech Stack — Why Each Was Chosen

| Tool | What it does here | Why this one |
|---|---|---|
| `mcp` (official SDK) | Handles all MCP protocol details | Official Anthropic SDK — most reliable |
| `Groq API` | Runs Llama 3.3 model | Fastest free LLM option available |
| `Llama 3.3 70B` | Does the actual code review | Best quality on Groq's free tier |
| `Starlette` | HTTP routing (`/` and `/mcp/`) | Lightweight, no unnecessary features |
| `Uvicorn` | Runs Starlette as web server | Industry standard Python ASGI server |
| `python-dotenv` | Reads `.env` file | Secure API key management |
| `Railway` | Hosts the server | Free tier, GitHub auto-deploy |

---

## What I Learned Building This

- **MCP protocol** — how tools are registered, discovered, and called
- **Transport types** — stdio vs SSE vs Streamable HTTP and when to use each
- **ASGI** — how modern Python web servers work (scope, receive, send)
- **Prompt engineering** — how wording affects LLM output quality
- **Debugging** — systematic elimination of errors (encoding, ports, transport versions)
- **Deployment** — environment variables, dynamic ports, Linux vs Windows packages

---

## Author

**Tharun Paluru** — Built as part of learning MCP and agentic AI development.

- GitHub: [@THARUN-PALURU](https://github.com/THARUN-PALURU)
- Built with guidance from Claude (Anthropic) — a real vibe-coding experience

---

*Built with [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Powered by [Groq](https://groq.com) | Deployed on [Railway](https://railway.app)*
