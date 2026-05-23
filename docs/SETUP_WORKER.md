# Cloudflare Worker Setup Guide

The Worker is a tiny proxy that holds API keys. The desktop app talks to the Worker, and the Worker talks to OpenAI / AssemblyAI / ElevenLabs. That way no API keys ever ship inside the app binary.

**For the MVP we only use the `/chat` endpoint**, but we deploy all of them so we don't have to touch the Worker later when we add voice.

---

## 1. Prerequisites

You need:

```bash
node --version    # 18+
npm --version     # 9+
```

If you don't have them:

```bash
# Node 20 LTS (Ubuntu/Debian)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

Plus:

- A **Cloudflare account** — https://dash.cloudflare.com/sign-up (free, no card required)
- An **OpenAI API key** — https://platform.openai.com/api-keys
- AssemblyAI and ElevenLabs keys are **optional for the MVP** — you can add them later when voice support lands

---

## 2. Install Worker dependencies

```bash
cd worker
npm install
```

This installs `wrangler` (Cloudflare's CLI) and the other dev tools.

---

## 3. Log into Cloudflare

```bash
npx wrangler login
```

A browser window opens; authorize with your Cloudflare account. When the terminal says "Successfully logged in", you're good.

---

## 4. Upload API keys to the Worker (as secrets)

**For the MVP, only OpenAI is required:**

```bash
npx wrangler secret put OPENAI_API_KEY
# Paste your key: sk-...
```

Optional (only needed once you wire up voice):

```bash
npx wrangler secret put ASSEMBLYAI_API_KEY
npx wrangler secret put ELEVENLABS_API_KEY
```

> **Note:** the Worker will deploy fine without the AssemblyAI/ElevenLabs secrets. The `/transcribe-token` and `/tts` endpoints will return 500 until those keys exist, but `/chat` will work.

---

## 5. Deploy the Worker

```bash
npx wrangler deploy
```

You'll see something like:

```
Published clicky-proxy (1.23 sec)
  https://clicky-proxy.<your-subdomain>.workers.dev
```

**Copy that URL** — you'll paste it into the Python app's `.env`.

---

## 6. Wire the URL into the Python app

Back at the project root:

```bash
cd ..
cp .env.example .env
```

Open `.env` and replace the placeholder with the URL you copied:

```
WORKER_URL=https://clicky-proxy.YOUR-SUBDOMAIN.workers.dev
```

---

## 7. Smoke-test the Worker

```bash
curl -X POST "$WORKER_URL/chat" \
  -H "content-type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "max_tokens": 50,
    "messages": [{"role": "user", "content": "say hi in one word"}]
  }'
```

If you get a JSON response back, the Worker is ready. A 401/403 means double-check your OpenAI key.

---

## 8. Local Worker dev (optional)

If you want to hack on the Worker without redeploying every time:

```bash
# Create worker/.dev.vars
echo "OPENAI_API_KEY=sk-..." > worker/.dev.vars

cd worker
npx wrangler dev
# Listens on http://localhost:8787
```

To use the local Worker, set this in `.env`:

```
WORKER_URL=http://localhost:8787
```

---

## Troubleshooting

| Error | Fix |
|---|---|
| `wrangler: command not found` | Make sure you ran `npm install` inside `worker/`; use `npx wrangler` |
| `Authentication error` (401) | Re-upload the key: `wrangler secret put OPENAI_API_KEY` |
| `model: ... not found` | Set `OPENAI_MODEL` in `.env` to a vision-capable model like `gpt-4o-mini` |
| Deploy asks for an Account ID | Cloudflare dashboard → top-right account menu → Account ID |
