# Installing MINT

**English** · [Русский](ru/INSTALL.md)

MINT runs on your own computer: the page opens in your browser at `http://localhost:8501` and is visible only
to you. Documents and the knowledge base stay on this computer; MINT connects only to the model APIs you put
into `.env`.

No administrator rights are needed — everything is installed into a `.venv` folder next to the program.

**In short:**

1. Python 3.10 or newer.
2. The MINT folder (`git clone` or a downloaded ZIP).
3. `install.sh` (Linux, macOS) or `install.bat` (Windows).
4. Fill in `.env`.
5. Start with `run_mint.sh` or `run_mint.bat`.

> The interface is available in English and Russian. MINT follows the language of your OS; to choose
> explicitly, set `MINT_LANG=en` (or `ru`) in `.env` — the self-check uses it too. The interface language can
> also be switched in the sidebar.

## What install.sh and run_mint.sh are for

MINT is a Python program that needs third-party packages: Streamlit (the web page), Docling (.docx parsing),
faiss (vector search) and a few more. The scripts install them for you with one command.

| Script | What it does | The same by hand |
|---|---|---|
| `install.sh` / `install.bat` | checks Python (3.10+) → creates a `.venv` folder next to the program → installs the packages of exact versions from `requirements.lock` (from the internet, a mirror or an offline bundle); recreates an incomplete `.venv` left by an interrupted install → creates `.env` from the template → runs the self-check | `python3 -m venv .venv`<br>`.venv/bin/pip install -r requirements.lock`<br>`cp .env.example .env`<br>`.venv/bin/python check_install.py` |
| `run_mint.sh` / `run_mint.bat` | changes to the MINT folder → starts Streamlit from `.venv` → opens the browser | `cd ~/mint`<br>`.venv/bin/python -m streamlit run app.py` |

**Why `.venv` instead of a plain `pip install`:**

- installing into the system needs administrator rights, a folder of your own does not;
- MINT's package versions do not conflict with other Python programs;
- nothing in the system changes: to remove MINT, delete its folder.

**You can skip the scripts** if the packages are already installed:

```bash
cd ~/mint
streamlit run app.py
```

Two caveats:

- `python app.py` does not work: Streamlit apps are started with `streamlit run`.
- Start MINT from its own folder. Otherwise Streamlit does not see `.streamlit/config.toml`, and the page
  becomes reachable from the network instead of only from your computer.

## Requirements

| | |
|---|---|
| Python | **3.10–3.12** (3.11 recommended). Docling does not support 3.9 and older |
| Disk | about 0.6 GB for packages, about 165 MB to download (no PyTorch, see [Package versions and Docling without PyTorch](#package-versions-and-docling-without-pytorch)); plus space for your knowledge base |
| Memory | 4 GB free or more; large documents take longer to parse |
| Models | an OpenAI-compatible API for an LLM and for embeddings (a reranker is optional), and an API key if the server needs one |
| Packages | from the internet, an internal PyPI mirror or an offline bundle (see below) |

> **Use only models you are allowed to use.** Put into `.env` only the models and gateways approved for your
> documents. Your API key is personal: do not share it or put `.env` into shared folders.

Prefer a short path without spaces for the MINT folder, e.g. `~/mint` or `C:\mint`.

No model server yet? [docs/OLLAMA.md](OLLAMA.md) shows how to run open models locally with Ollama.

## Linux and macOS

```bash
git clone https://github.com/Sdorenskiy/mint.git ~/mint
cd ~/mint
./install.sh            # packages from the internet or an internal mirror
./install.sh wheels     # offline: from a bundle (a "wheels" folder)
```

The script creates `.venv`, installs the packages of exact versions from `requirements.lock`, creates `.env`
from the template and runs the self-check. If the system lacks the `python3-venv` package (Debian, Ubuntu,
Astra), the script creates the environment without it and downloads pip with the system pip (your mirror
settings) or takes it from the offline bundle — no administrator needed. An incomplete `.venv` left by an
interrupted attempt is recreated automatically; to start from scratch: `./install.sh --clean`. To use a specific interpreter: `PYTHON=/path/to/python3.11 ./install.sh`.

macOS is expected to work the same way but has not been tested yet.

If pip cannot reach the internet but your organisation has a PyPI mirror (Nexus, Artifactory — ask IT for the
address):

```bash
python3 -m pip config set global.index-url https://<mirror>/simple
python3 -m pip config set global.cert /path/to/corporate-ca.crt   # if the mirror uses an internal certificate
```

### Astra Linux

[Astra Linux](https://astralinux.ru) is a Russian Debian-based distribution.

- **Astra Linux 1.8** ships Python 3.11 — fine.
- **Astra Linux 1.7** ships Python 3.7 — MINT will not run on it. Options: upgrade to 1.8, use Python 3.10+
  installed by an administrator, or use another computer or a shared server.
- If the **closed software environment (ЗПС)** is enabled, unsigned libraries installed by pip (numpy, faiss…)
  will not load (`Operation not permitted` on import); `check_install.py` reports this. Only an administrator
  can resolve it (by signing the libraries or adding an exception) — do not try to bypass it.

Check the version with `cat /etc/astra_version` and `python3 --version`.

## Windows

The automated tests run on Windows; real-world use on Windows has not been reported yet — if something
fails, please open an issue with the output of `check_install.py`.

### 1. Python

Install Python 3.11 or 3.12 from [python.org](https://www.python.org/downloads/windows/). Choose
**"Install for me only"** (no administrator rights needed). Check in a command prompt:

```bat
py -3 --version
```

### 2. Install

Unpack MINT, e.g. to `C:\mint`, and double-click `install.bat`. For an offline bundle run from the MINT folder:

```bat
install.bat wheels
```

If `.bat` files are blocked by policy or antivirus, run the same steps by hand:

```bat
cd C:\mint
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
copy .env.example .env
.venv\Scripts\python check_install.py
.venv\Scripts\python -m streamlit run app.py
```

### 3. Corporate certificates

Internal gateways usually use the organisation's own certificate. On Windows MINT verifies certificates
against the Windows certificate store (the `truststore` package). If you still get
`CERTIFICATE_VERIFY_FAILED`:

1. Export your organisation's root certificate to a `.pem` file (Base64).
2. Point to it in `.env`: `CA_BUNDLE_PATH=C:\mint\corp-ca.pem`.

On Linux, MINT uses the system bundle `/etc/ssl/certs/ca-certificates.crt` by default.

### 4. Editing `.env` in Notepad

When saving, choose **"All files"** as the type and `.env` as the name — otherwise you get `.env.txt`, which
MINT does not see. UTF-8 and Windows-1251 encodings both work.

## Fill in `.env`

Open `.env` in the MINT folder (the install script created it from `.env.example`) and set:

```ini
LLM_API_URL=https://<gateway>/v1                 # base URL, without /chat/completions
EMBED_API_URL=https://<gateway>/v1/embeddings
LLM_API_KEY=<your key>                           # empty for servers without authentication
LLM_MODEL=<model>                                # empty: the first model the server lists
EMBED_MODEL=<embedding model>
RERANK_API_URL=https://<gateway>/v1/rerank       # optional, improves accuracy
RERANK_MODEL=<reranker model>
```

Everything else can stay as is. The knowledge base is stored in `~/knowledge_base`, logs and feedback in
`~/mint_logs` by default. To fix the interface language, add `MINT_LANG=en` (or `ru`).

## Check the installation

```bash
.venv/bin/python check_install.py          # Linux, macOS
.venv\Scripts\python check_install.py      # Windows
```

The self-check goes step by step:

1. Python and packages.
2. Parsing a test .docx.
3. `.env` and folders.
4. Connections to the models, including one short request to the LLM (skip with `--no-llm`).
5. Streamlit settings.
6. Smoke test: the MINT page opens on real Streamlit without a browser (skip with `--skip-page`).

Every error comes with a hint. The output contains no keys, so it can be shared as is.

## Start

```bash
./run_mint.sh        # Linux, macOS
run_mint.bat         # Windows — double-click
```

The browser opens by itself, or go to `http://localhost:8501`. Stop with Ctrl+C (or close the console window).

First steps:

1. Upload reference documents into the knowledge base (sidebar → knowledge base).
2. Ask a question in the chat tab.
3. Review a document in the document review tab.

Rate results with 👍/👎 — feedback is collected in `~/mint_logs/feedback.jsonl` and can be downloaded from the
sidebar.

> Feedback contains questions, answers and quotes from your documents — share the file only where those
> documents may be shared.

## Offline bundle

For computers where pip cannot reach the internet. Build the bundle on a computer that can, **with the same OS
and the same Python version** as the target.

Linux / macOS:

```bash
cd ~/mint
python3 -m pip download -r requirements.lock -d wheels     # or requirements.txt if there is no lock file
python3 -m pip download pip -d wheels                      # pip itself, for systems without python3-venv
```

Windows:

```bat
cd C:\mint
py -3 -m pip download -r requirements.lock -d wheels
```

Copy the MINT folder together with `wheels` — but **without** `.env`, `knowledge_base`, `mint_logs` and your
documents — using a transfer method allowed in your organisation. On the target computer run
`./install.sh wheels` or `install.bat wheels`.

Building a Linux bundle on another OS works only if every package has a prebuilt wheel; if pip reports a
package without one, build the bundle on a matching machine:

```bash
python3 -m pip download -r requirements.lock -d wheels --only-binary=:all: \
    --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 \
    --python-version 3.11 --implementation cp
```

## Package versions and Docling without PyTorch

**Exact versions.** `install.sh` and `install.bat` install the packages from `requirements.lock` — exact versions,
one file for Linux, Windows and macOS (with markers for Python versions and OSes). These are what GitHub tests on
every change and every night: a fresh install on Ubuntu (Python 3.10–3.12), Debian 12 without `python3-venv` (as
Astra Linux 1.8) and Windows, then .docx parsing with the real Docling, base → chat → review and the self-check
(`.github/workflows/install.yml`, `tests/test_real_install.py`). If your mirror lacks one of the exact versions,
the script says so and installs from `requirements.txt`.

Updating the versions (for maintainers): change `requirements.txt`, rebuild the lock file and wait for a green
installation check on GitHub:

```bash
pip install uv
uv pip compile requirements.txt --universal --python-version 3.10 --no-header -o requirements.lock
```

**Docling without PyTorch.** .docx is read by Docling — its Word backend: heading styles, lists, tables, no models.
MINT calls this backend directly rather than through Docling's general converter, which on start also loads PDF
parsing with models (PyTorch). The result is the same as the full Docling through its converter — GitHub compares
them on Docling's test documents and MINT's own samples (`tools/docx_parity.py`; to check on your own documents
with the full Docling installed: `python tools/docx_parity.py folder_with_docx`). So the slim build
`docling-slim[format-docx]` of an exact version is installed:

| | MINT (slim Docling) | with the full Docling |
|---|---|---|
| Packages | 72 | 122 |
| Download | about 165 MB | about 540 MB (CPU PyTorch) — gigabytes with GPU PyTorch |
| On disk | about 0.6 GB | about 2.1 GB |
| Model libraries (PyTorch, transformers, huggingface_hub, OpenCV) | none | present |

Fewer packages mean less for an information-security review, and no libraries that can download models from the
internet by themselves. .pdf is read by MINT itself (pdfplumber), also without models.

If the full Docling is already installed (for example, MINT runs on the system Python), nothing needs to change:
MINT takes the same Word backend from it.

## Updating

Stop MINT and run `update.sh` (Windows: `update.bat`) in the program folder with the archive of the new version:

```bash
./update.sh ~/Downloads/mint-21.2.zip       # or a .tar.gz, or the unpacked folder of the new version
```

The script replaces the code (the `mint`, `docs`, `tools`, `tests` and `static` folders entirely, so that removed
files do not stay), keeps your `.env`, `config.yaml`, `glossary.json`, `checklists.yaml`, `prompts.yaml` and
`.venv` (they are never taken from the archive, even if it has them) and runs `install.sh` itself: it adds new
packages and checks the installation. Offline, pass the offline bundle folder as the second argument
(`./update.sh mint.zip wheels`); if it is inside the new version, the script finds it. The version number is at the
bottom of the sidebar ("MINT version").

By hand: replace the program files with the new ones, keeping the files listed above, and run `./install.sh` again.

The knowledge base lives separately (`KB_DIR`) and is not touched by an update. If a new version needs
re-indexing, the sidebar will say so.

## Troubleshooting

| Message | What to do |
|---|---|
| `Port 8501 is already in use` | MINT is already running — open `http://localhost:8501`. A second instance: `./run_mint.sh --server.port 8502` |
| `.env не найден` (.env not found) | The file must be named exactly `.env` and sit next to `app.py`. The self-check shows where MINT looked |
| `CERTIFICATE_VERIFY_FAILED` | Set your organisation's certificate in `CA_BUNDLE_PATH` (see [Corporate certificates](#3-corporate-certificates)) |
| HTTP 401 / 403 | Wrong or expired key, or no access to the model |
| HTTP 404 | Wrong address: `LLM_API_URL` is the base URL without `/chat/completions`, `EMBED_API_URL` is the full `/embeddings` URL |
| `Operation not permitted` on import | Astra Linux closed software environment — see [Astra Linux](#astra-linux) |
| `python` / `py` not found (Windows) | Reinstall Python from python.org; the `py` launcher is installed by default |
| The first document upload is slow | Docling is loaded into memory on first use; later uploads are faster |
| `Incomplete .venv` / `No module named pip` | An incomplete `.venv` was left by an interrupted install — `install.sh` recreates it by itself; to force it: `./install.sh --clean` |
| No `python3-venv` package | No administrator needed: `install.sh` downloads pip with the system pip (your mirror settings). Without a system pip either — an offline bundle with `pip-*.whl` |
| `No module named 'torch'` or `'docling_parse'` when uploading a .docx | The packages are not from `requirements.lock` (another Docling): `./install.sh --clean` (Windows: `install.bat --clean`) |
| `Some exact versions are not available` | Your mirror lacks one exact version — the script installs from `requirements.txt` by itself; tell the maintainer which package |
| The installation stopped with a pip error | The end of the log is on screen; the full pip output is in `.venv/install.log` (Windows: `.venv\install.log`) — send that file |
| `GOST engine already loaded` | A message of the Astra system cryptography (the GOST engine in OpenSSL), not of MINT; harmless |
