# Trying MINT with open models (Ollama)

**English** · [Русский](ru/OLLAMA.md)

To try MINT without an LLM gateway: [Ollama](https://ollama.com) runs open models on your computer and MINT
connects to it through its OpenAI-compatible API.

> At work, use only the models and gateways approved by your organisation. This setup is meant for tests on
> public documents (e.g. published standards).

Default models:

- `qwen2.5:3b` — the language model, about 2 GB, handles Russian and English reasonably well and runs on a CPU;
- `bge-m3` — embeddings, about 1.2 GB, multilingual.

Ollama has no reranker: search works without it, but less accurately.

## Option 1: Docker

You need Docker with Compose.

```bash
git clone https://github.com/Sdorenskiy/mint.git && cd mint
docker compose up -d --build
docker compose logs -f ollama-pull     # wait until both models are downloaded
```

Open `http://localhost:8501`. The knowledge base and logs live in the `mint-data` volume and survive restarts.

Other models (check that they exist in the [Ollama library](https://ollama.com/library) first):

```bash
MINT_LLM=qwen2.5:7b MINT_EMBED=bge-m3 docker compose up -d
```

If you change the embedding model, documents must be re-indexed; MINT offers this in the sidebar.

Stop with `docker compose down`. To also delete the downloaded models and the knowledge base:
`docker compose down -v`.

With an NVIDIA GPU, answers are many times faster: add a `deploy.resources.reservations.devices` block to the
`ollama` service in `docker-compose.yml` (see the Ollama and Docker documentation).

## Option 2: Ollama on your computer, MINT from source

1. Install Ollama and pull the models:

   ```bash
   ollama pull qwen2.5:3b
   ollama pull bge-m3
   ```

2. Set the context window. Ollama's default window is small and long requests get truncated:

   ```bash
   OLLAMA_CONTEXT_LENGTH=8192 ollama serve
   ```

   On Windows, set the environment variable `OLLAMA_CONTEXT_LENGTH=8192` and restart Ollama.

3. Install MINT as described in [INSTALL.md](INSTALL.md) and put into `.env`:

   ```ini
   LLM_API_URL=http://localhost:11434/v1
   EMBED_API_URL=http://localhost:11434/v1/embeddings
   LLM_API_KEY=
   LLM_MODEL=qwen2.5:3b
   EMBED_MODEL=bge-m3
   MINT_CONFIG=config.ollama.yaml
   ```

4. Run `python check_install.py`, then start `run_mint.sh` / `run_mint.bat`.

## What to expect

- Small models are noticeably weaker than large hosted ones: the review finds less and makes more mistakes.
  That is enough to evaluate the interface and search, not to judge review quality.
- On a CPU an answer takes from tens of seconds to several minutes, and reviewing a large document takes a
  long time — try a 5–10 page document first.
- Ollama does not report model windows; they are set in `config.ollama.yaml`. If you change
  `OLLAMA_CONTEXT_LENGTH`, change `llm_context_tokens` too.
