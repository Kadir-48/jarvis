# L.A.I.K.A. — Local Setup

**L.A.I.K.A.** means **Life, Academics, & Intelligence Kinetic Assistant**.

This repository is a personal, educational configuration of [Jarvis by Baris Sencan](https://github.com/isair/jarvis). The upstream application supplies the desktop interface, voice pipeline, local-model integration, memory, planning and tool system. This fork keeps the upstream architecture intact while adding a low-resource starting profile for the L.A.I.K.A. project.

## Target machine

Initial target: Linux Mint 22.x, Intel Core i3-1215U, 8 GB RAM, integrated Intel graphics.

This is a constrained CPU-only setup. Expect slower responses than a machine with a dedicated GPU. Do not run several large local models simultaneously.

## Local-only starting profile

Use `examples/laika-low-resource-config.json` as a set of overrides for Jarvis' normal configuration. It is intentionally conservative:

- Ollama at `127.0.0.1:11434`; no paid API or API key.
- Existing chat model: `qwen2.5:1.5b`.
- Whisper Base with INT8 compute instead of the much larger Medium model.
- Low Power Mode enabled.
- Local speech output through Piper.
- Location and background tasks disabled initially.

The profile does not promise that every feature will run smoothly within 8 GB RAM. If the machine becomes unresponsive, close the assistant and reduce background applications before changing model sizes.

## First-run sequence

1. Download the **Linux x64** release from the [upstream releases page](https://github.com/isair/jarvis/releases). Choose the release asset named `Jarvis-Linux-x64.tar.gz`.
2. Extract it in your home directory. Do not use `sudo` or install system-wide.
3. Start the extracted `Jarvis/Jarvis` application.
4. In the setup wizard, select **Ollama** and use `http://127.0.0.1:11434`.
5. Select `qwen2.5:1.5b` for chat and the Base Whisper model. Enable Low Power Mode.
6. Apply the overrides in `examples/laika-low-resource-config.json` only if the wizard does not already save those choices.
7. Test text chat first, then microphone input, then speech output. Test one feature at a time.

The exact release and Linux dependencies can change. If the app fails to start, use its Logs output and the upstream troubleshooting guide rather than installing packages blindly.

## Safety defaults

L.A.I.K.A. should ask before consequential actions. Keep file changes, application installation, sending messages, purchases, account changes and other irreversible actions behind explicit user confirmation. Review every MCP server and its permissions before enabling it. Do not expose the local Ollama port to the public internet.

## Current scope

This first fork stage is a configuration and documentation baseline, not a completed rebrand or a claim that every requested computer-control feature is implemented. Future code changes should be made on the `laika/customization` branch, tested on Linux, and kept separate from upstream updates.

## Upstream attribution and license

The underlying Jarvis project is by Baris Sencan. Its repository license permits personal, educational and research use, requires retaining the notice, and prohibits commercial use without a separate license. See [LICENSE](LICENSE) before redistributing or using this fork beyond personal/educational purposes.
