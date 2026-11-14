# L.A.I.K.A. local tools for Fono

This folder is the first safe, local computer-tools layer for L.A.I.K.A.
It is designed to work with Fono as the voice front end and an existing
local Ollama model as the assistant brain.

## Why this design

- Fono supplies a lightweight Linux voice stack: hotkeys, local speech
  recognition, spoken responses, wake-word option, history, and local model
  support.
- The local Ollama model remains the language model; no paid API is required.
- This MCP server adds a separate tool layer for laptop tasks.
- The first version is deliberately read-only except for opening an app or
  website. It has no shell execution, file writes, deletion, package installs,
  or administrator operations.

## Supported actions

- Read basic system status (OS, memory, free disk).
- List files in Desktop, Documents, Downloads, LAIKA, and Applications.
- Search file names in those locations.
- Read small text/source files (64 KiB maximum).
- Find and launch installed desktop applications.
- Open an explicitly requested HTTP(S) website.

Sensitive/hidden folders and common secret filenames are blocked. Paths are
resolved before access so traversal and symlink escapes cannot leave the
approved folders. The server binds only to 127.0.0.1.

## Runtime

Requires Python 3.11+ and uses only the Python standard library.

Start it with:

    python3 laika/mcp_server.py

Health check: http://127.0.0.1:8765/health
MCP endpoint: http://127.0.0.1:8765/mcp

No sudo, pip install, virtual environment, or extra Python packages are
required for this tool server.

## Connect it to Fono

In Fono settings, enable Assistant → Tools & actions, then add an MCP server:
- Name: LAIKA Local Tools
- URL: http://127.0.0.1:8765/mcp

Fono supports Streamable HTTP MCP endpoints for URLs that do not end in /sse.
Keep this endpoint on loopback; do not expose it to the LAN.

Equivalent TOML configuration:

    [assistant.tools]
    enabled = true

    [[assistant.tools.mcp]]
    name = "LAIKA Local Tools"
    url = "http://127.0.0.1:8765/mcp"

## Current limitations

This is a safe first layer, not yet a full autonomous desktop operator.
It intentionally does not execute terminal commands, install software,
modify files, send messages, or perform irreversible actions. Those
capabilities need explicit user confirmation and narrow allowlists before
they are added.

Fono's normal desktop installer currently uses administrator privileges.
The MCP server itself does not. A no-admin Fono runtime path must be verified
on the target Linux Mint machine before claiming the complete setup is ready.
