# Security

**English** · [Русский — черновик для согласования с ИБ](ru/SECURITY.md)

This page describes what MINT sends where, what it stores, and the known risks — useful for anyone installing
it in an organisation. To report a vulnerability, please use GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
for this repository instead of a public issue.

## Data flows

```
Browser ──HTTP, localhost──► MINT (Python, Streamlit) ──HTTPS──► your model endpoints
                                   │                             (LLM, embeddings, reranker)
                                   └── local files: knowledge base, logs, feedback
```

- **Outgoing connections** go only to the addresses in `.env`: the LLM, embedding and reranker APIs.
  - Streamlit usage statistics are disabled (`.streamlit/config.toml`: `gatherUsageStats = false`).
  - The page loads nothing from the internet: the interface fonts are files in `static/fonts/`, served by
    Streamlit itself (`enableStaticServing = true`, only the `static/` folder is served, at `app/static/`).
  - Only .docx documents are accepted. For .docx, Docling uses no neural models and downloads nothing.
    You can verify this by running `check_install.py` without internet access.
- **Incoming connections:** none by default. The page listens on `localhost:8501` only
  (`server.address = "localhost"`), so other computers cannot reach it.
- **What is sent to the models:** fragments of documents from the knowledge base and of the document under
  review (the consultant sends more: whole sections and system cards, up to 60,000 characters per request by
  default, `consult_context_max_chars`), user questions (in the consultant — also the earlier turns of the
  conversation), and review comments. If your documents contain personal or otherwise protected data,
  the model endpoint must be approved for it.

## What is stored where

| Location | Contents | Contains document text |
|---|---|---|
| `KB_DIR` (default `~/knowledge_base`) | document fragments (`parent_store.json`), vectors (FAISS), BM25 index, metadata, the original uploaded .docx files (`sources/`), extracted abbreviations | yes |
| `LOG_DIR` (default `~/mint_logs`) | `mint_system.log` (rotated, 10 MB × 5): beginnings of queries (up to 120 characters), file names, errors | partly |
| `LOG_DIR/feedback.jsonl` | 👍/👎 ratings with the question (the consultant request), answer, sources and comment | yes |
| `LOG_DIR/eval/` | quality checks: questions with verbatim phrases from the documents, reports, chat answers | yes |
| `LOG_DIR/audits/` | saved reviews ("📂 Saved reviews"): the report, the log, raw model answers (compressed), a copy of the reviewed .docx, the expert assessment of findings; removed with "🗑️ Delete the review" | yes |
| `.env` in the program folder | API addresses and the **API key** | no |
| `prompts.yaml` in the program folder (`PROMPTS_PATH`) | your edits of the model prompts saved on the "📝 Prompts" page | no |
| process memory | chat history and the consultant conversation (with the fragments found), results of the current session; gone when the tab is closed or MINT restarts | yes |

The assessment file for improving MINT ("📤 Download the assessment", "📥 Download the assessments") is downloaded
by the user. With texts (the default) it has the findings with quotes from the document; with "Without finding
texts" — only check kinds, severity, marks and reasons, no texts, quotes, sections, comments or file names.

Recommendations:

- **Permissions.** Only the account that runs MINT should have access to `KB_DIR`, `LOG_DIR` and `.env`
  (`chmod 700` on the folders, `chmod 600` on `.env`).
- **Prompt edits.** Anyone who can open MINT can save a prompt edit for everyone ("📝 Prompts" → Save). The
  prompt version and the list of edited prompts are recorded with ratings, review logs and quality checks. On a
  shared server, make `prompts.yaml` read-only for the MINT account if edits should go through an
  administrator: the page then reports that saving failed, and "Try in this session" still works.
- **Pickle files.** The knowledge base files `*.pkl` are loaded with Python's pickle. Never let others write
  into that folder, and never load a knowledge base from an untrusted source.
- **Backups.** Back up `KB_DIR` according to the rules for documents of that category.

## Secrets

- The API key lives in `.env`, which is excluded from the repository by `.gitignore`.
- MINT does not write keys to its log. The self-check `check_install.py` only reports whether a key is set.
- TLS verification is on:
  - a corporate CA is set with `CA_BUNDLE_PATH`;
  - on Windows the system certificate store is used;
  - `SSL_INSECURE=1` disables verification. It is meant only for debugging in an internal network, and MINT
    logs a warning when it is set.

## Dependencies

| Package | Purpose | License |
|---|---|---|
| Streamlit | web interface | Apache 2.0 |
| Docling (slim build `docling-slim`, .docx reader only: no PyTorch, no models) | .docx parsing | MIT |
| pdfplumber (with pdfminer.six and pypdfium2) | .pdf parsing from the text layer, without models; no network access | MIT; pypdfium2: Apache 2.0 / BSD-3 |
| faiss-cpu | vector search | MIT |
| NumPy | numerics | BSD |
| requests | HTTPS calls to the APIs | Apache 2.0 |
| python-docx | reading and writing .docx | MIT |
| python-dotenv | reading `.env` | BSD |
| PyYAML | reading model prompts (`mint/prompts/*.yaml`) and `config.yaml` | MIT |
| truststore | OS certificate store | MIT |

Pin exact versions with `requirements.lock` (see [INSTALL.md](INSTALL.md#pinning-versions-for-maintainers)).

## Known risks and limitations

- **No authentication or access control.** This is fine locally, because the page is reachable only from the
  user's own computer. For a shared server, see below.
- **One knowledge base per instance.** All users of one instance share its knowledge base. Documents under
  review, chat history and reports are per session and kept in memory.
- **Instructions inside documents** (prompt injection). Document text can influence the model's output.
  Results are advisory, and source links let users verify them.
- **Model errors.** The model can miss an issue or be wrong. MINT supports expert review; it does not replace
  it.

## Running on a shared server

| Measure | How |
|---|---|
| Isolation | A dedicated VM or container (`Dockerfile`) and a service account without administrator rights |
| Access | A reverse proxy (nginx etc.) with your organisation's authentication (SSO/LDAP) and TLS. MINT listens only on `127.0.0.1` behind the proxy |
| Network | Outgoing traffic only to the model endpoints; incoming only from the proxy |
| Streamlit | Set `server.address = "127.0.0.1"`, `server.fileWatcherType = "none"`, and `server.maxUploadSize` as needed. XSRF protection is on by default (`server.enableXsrfProtection`) |
| Data | Only the service account can access `KB_DIR`, `LOG_DIR` and `.env`. Back up the knowledge base and rotate the logs |
| Separate bases | If documents of different departments must not be mixed, run one instance per department, each with its own `KB_DIR` |
