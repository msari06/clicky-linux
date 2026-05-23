# Clicky for Linux

> A Linux port of [**clicky.so**](https://clicky.so) — the original macOS Clicky by [@farzaa](https://github.com/farzaa/clicky).
> This project is **dedicated to the original Clicky**. All credit for the idea, the design, and the vibe goes to the original author; this repository is just a gift to the Linux community so we can play with the same thing.
> Built from scratch for X11 + PyQt6, with the macOS app's behavior as the reference.

Clicky is the little AI buddy that lives next to your cursor. Hit a hotkey, ask a question about whatever is on your screen, and a streaming bubble answers right there — and if the model points to something, a blue cursor flies over and taps it.

Clicky has two modes you can flip between in the input bar:

- **Vision mode** (default): screenshot + question → OpenAI vision via your Cloudflare Worker → answer streams into a bubble, optionally pointing at something on screen.
- **Code mode**: prompt → spawns `claude -p` ([Claude Code](https://docs.anthropic.com/en/docs/claude-code)) as a subprocess in a configured workspace → its progress (text + tool calls) streams into the same bubble. Lets you ask Clicky to *do* things in a directory, not just describe what it sees.

## Quick start

```bash
# 1. Check system dependencies
make check-system

# 2. (If missing) install the recommended apt packages
sudo apt install -y python3-venv libxcb-cursor0 libxkbcommon0 libegl1 libgl1 libfontconfig1 libdbus-1-3

# 3. Install Python deps (uses uv)
make install

# 4. Set up and deploy the Cloudflare Worker (see docs/SETUP_WORKER.md)
make worker-install
cd worker && npx wrangler login && npx wrangler secret put OPENAI_API_KEY && npx wrangler deploy

# 5. Point the app at the worker
cp .env.example .env
# Open .env in your editor and set WORKER_URL=... to the URL wrangler printed

# 6. Run it
make run
```

A blue triangle icon shows up in the system tray. Press **Ctrl+Alt+Space** to open the input.

## Code mode (Claude Code agent)

Click the small `vision` / `code` pill on the left of the input bar to switch. In Code mode:

- Your prompt is handed to a `claude -p` subprocess in the workspace shown under the input. Click the workspace chip to pick a different directory.
- For one-off overrides, start your prompt with `@/path/to/dir ` (or `@"/path with spaces" `) — that directory is used as the cwd for that single call.
- The bubble streams Claude Code's prose and shows compact tool chips (`› Read foo.py`, `✎ Edit bar.py`, etc.) so you can see what it's doing.
- **Shell commands are blocked by default**. Flip the `shell: off` pill to `shell: on` to allow `Bash` — you'll get a confirmation dialog the first time, because this opens the door to `rm`, `git push`, package installs, and anything else the model decides to run. Toggle off when you don't need it.
- File edits go through with `--permission-mode acceptEdits`; check `git diff` if you want to review what changed.

Requirements: [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated (`claude auth`). Clicky calls the `claude` binary from PATH; override with `CLAUDE_CODE_PATH` in `.env`.

## Architecture (short version)

```
Hotkey (pynput, X11)
   ↓
Overlay (transparent fullscreen PyQt6 window)
   ↓ user types and presses Enter
Screenshot (mss, all monitors)
   ↓
Cloudflare Worker /chat → OpenAI API
   ↓ SSE stream
Bubble UI (text streaming)
   ↓ [POINT:x,y] if present
Blue cursor bezier animation
```

| Part | File | macOS counterpart |
|---|---|---|
| State machine | `clicky/state.py` | `CompanionManager.swift` |
| LLM streaming client | `clicky/llm/claude.py` | `ClaudeAPI.swift` |
| POINT parser | `clicky/llm/point_parser.py` | `CompanionManager.parsePointingCoordinates` |
| Screenshot | `clicky/screen/capture.py` | `CompanionScreenCaptureUtility.swift` |
| Hotkey | `clicky/input/hotkey.py` | `GlobalPushToTalkShortcutMonitor.swift` |
| Tray | `clicky/ui/tray.py` | `MenuBarPanelManager.swift` |
| Panel | `clicky/ui/panel.py` | `CompanionPanelView.swift` |
| Overlay + cursor | `clicky/ui/overlay.py`, `cursor.py` | `OverlayWindow.swift` |
| Response bubble | `clicky/ui/response_bubble.py` | `CompanionResponseOverlay.swift` |
| Worker proxy | `worker/src/index.ts` | same idea, OpenAI-flavored |
| Claude Code agent | `clicky/llm/claude_code.py` | (new — no macOS counterpart yet) |
| Mode + workspace persistence | `clicky/state_store.py` | (new — no macOS counterpart yet) |

## Linux-specific choices

- **X11 + GNOME** is the primary target. On Wayland, `pynput` global hotkeys don't work reliably on most setups — that path will come later.
- **Default hotkey is `Ctrl+Alt+Space`** (modifier-only `Ctrl+Alt` doesn't trigger reliably on Linux). Override it in `.env`.
- **GNOME 45+**: you need the [AppIndicator and KStatusNotifierItem Support](https://extensions.gnome.org/extension/615/appindicator-support/) extension for the tray icon to show up.
- **Screenshot downscaling**: each monitor is resized to a 1600 px long edge before sending — keeps payloads small, and the app rescales the model's coordinates back to real pixels.
- **Cursor**: we don't touch the real system cursor (forbidden on Wayland, rude on X11). Instead we draw our own blue triangle on a transparent overlay — the original Clicky does the same.

## Development

```bash
make worker-dev      # Run the worker locally at http://localhost:8787
# Set WORKER_URL=http://localhost:8787 in .env

make dev             # Run the app with DEBUG logging
```

## Roadmap

- [x] Code mode — Claude Code subprocess as a Clicky backend
- [ ] Native GUI tools (click, type, scroll) via OpenAI tool-calling, with per-action confirmation bubbles
- [ ] Per-tool confirmation in Code mode via Claude Code `PreToolUse` hooks (IPC socket)
- [ ] Microphone + AssemblyAI streaming (push-to-talk)
- [ ] ElevenLabs TTS playback
- [ ] Wayland fallback (XDG Portal screenshot, evdev hotkey)
- [ ] Onboarding flow
- [ ] PyInstaller single-file binary
- [ ] Conversation history persistence

## Credits

- Original idea, design, and macOS implementation: [**clicky.so**](https://clicky.so) by [@farzaa](https://github.com/farzaa/clicky). Go look at the original — it's the real deal.
- This repo: a from-scratch Linux re-implementation in Python/PyQt6, written as a tribute so Linux users can run something close to the same experience.

## License

MIT (matches the original Clicky).
