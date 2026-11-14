# L.A.I.K.A. local tools and voice foundation

This folder contains the first working integration layer for L.A.I.K.A.

- Fono v0.20.1 CPU binary is the Linux voice front end.
- Existing Ollama + qwen2.5:1.5b remains the local language model.
- The MCP server supplies safe local laptop tools.
- The installer is user-scoped: no sudo, apt, global Python packages, or
  system-library replacement.

## One-command setup

From the repository root:

    bash laika/install-user.sh

The script checks the CPU architecture, Python version, existing Ollama
server and model; downloads the pinned Fono binary; verifies its SHA-256;
installs into ~/.local; configures Fono to use local Ollama; starts the
loopback-only MCP service; and creates user-session autostart entries.

It does not install or download an AI model. It uses the already installed
qwen2.5:1.5b model. It preserves an existing Fono config as
config.toml.before-laika before writing the L.A.I.K.A. profile.

## Voice controls

- F7: dictate into the focused application.
- F8: ask the local assistant and hear the reply.
- Escape: cancel recording or stop speech.

## First safe computer tools

- Basic laptop status.
- List and search files in Desktop, Documents, Downloads, LAIKA, Applications.
- Read small text/source files.
- Find and launch installed desktop apps.
- Open an explicitly requested website.

The tools server binds only to 127.0.0.1. It has no shell execution,
arbitrary file writes, file deletion, package installation, or admin tools.
Sensitive/hidden paths and common secret filenames are blocked.

## Important limits

The initial 1.5B model is small and may make mistakes, especially with tool
selection. The first version is deliberately limited to low-risk operations.
File modification, sending messages, account changes, installations and
irreversible actions are not exposed as tools.

The Fono release is built on Ubuntu 22.04 (glibc 2.35), so its Linux binary
has a lower glibc baseline than the Jarvis archive that failed on Mint.
Linux Mint 22.3's glibc 2.39 satisfies that baseline. The binary is pinned
to v0.20.1 and verified by SHA-256 before installation.

## Remove only this L.A.I.K.A. layer

Stop and disable the user service (if systemd user services are available):

    systemctl --user disable --now laika-mcp.service

Then remove only these L.A.I.K.A.-created paths:

    ~/.config/systemd/user/laika-mcp.service
    ~/.config/autostart/laika-mcp.desktop
    ~/.config/autostart/laika-fono.desktop
    ~/.local/share/laika
    ~/.local/bin/fono
    ~/.config/fono/config.toml

Do not remove Ollama or its model. The installer keeps the prior Fono config
as config.toml.before-laika if one existed.
