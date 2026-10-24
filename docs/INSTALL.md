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
| `install.sh` / `install.bat` | checks Python (3.10+) → creates a `.venv` folder next to the program → installs the packages from `requirements.txt` (from the internet, a mirror or an offline bundle) → creates `.env` from the template → runs the self-check | `python3 -m venv .venv`<br>`.venv/bin/pip install -r requirements.txt`<br>`cp .env.example .env`<br>`.venv/bin/python check_install.py` |
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
| Disk | about 0.6 GB for packages (no PyTorch, see [Pinning versions](#pinning-versions-for-maintainers)); plus space for your knowledge base |
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

The script creates `.venv`, installs the packages (from `requirements.lock` if present, otherwise from
`requirements.txt`), creates `.env` from the template and runs the self-check. If the system lacks the
`python3-venv` package (Debian, Ubuntu, Astra), the script creates the environment without it and takes pip
from the offline bundle. To use a specific interpreter: `PYTHON=/path/to/python3.11 ./install.sh`.

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
.venv\Scripts\python -m pip install -r requirements.txt
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
py -3 -m pip download -r requirements.txt -d wheels
```

Copy the MINT folder together with `wheels` — but **without** `.env`, `knowledge_base`, `mint_logs` and your
documents — using a transfer method allowed in your organisation. On the target computer run
`./install.sh wheels` or `install.bat wheels`.

Building a Linux bundle on another OS works only if every package has a prebuilt wheel; if pip reports a
package without one, build the bundle on a matching machine:

```bash
python3 -m pip download -r requirements.txt -d wheels --only-binary=:all: \
    --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 \
    --python-version 3.11 --implementation cp
```

## Pinning versions (for maintainers)

To give everyone exactly the versions tested on a working machine, freeze them from `.venv`:

```bash
.venv/bin/python -m pip freeze > requirements.lock              # Linux
.venv\Scripts\python -m pip freeze > requirements-windows.lock  # Windows
```

The install scripts pick up the lock file automatically. Linux and Windows lists differ: each contains
OS-specific packages.

**Docling without PyTorch.** `requirements.txt` installs Docling's slim build, `docling-slim[format-docx]`: only
the .docx reader, no PyTorch, no OpenCV, no models — 66 packages and about 0.6 GB instead of 114 packages and
2.1 GB with the full `docling` (checked with 2.140). MINT does not need the rest: .pdf is read by pdfplumber,
also without models. Fewer packages also means less for an information-security review.

If your mirror has no `docling-slim` (an older Docling), replace that line in `requirements.txt` with
`docling>=2.0`. MINT works the same, but pip pulls PyTorch; on a computer without a GPU install its CPU build
first, to avoid gigabytes of CUDA libraries:

```bash
.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## Updating

Stop MINT and run `update.sh` (Windows: `update.bat`) in the program folder with the archive of the new version:

```bash
./update.sh ~/Downloads/mint-21.0.zip       # or the unpacked folder of the new version
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
