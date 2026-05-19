# Assistify RAG — Local setup and run guide (Windows)

Assistify is a help-desk stack with three FastAPI services:

| Service | Port (default) | Role |
|---------|----------------|------|
| **Login** | `7001` | Auth, sessions, Web UI entry |
| **RAG** | `7000` | Retrieval, speech, chat WebSocket |
| **LLM API** | `8000` or `8010` | Thin API in front of **Ollama** (optional shim) |

**Inference** is handled by **[Ollama](https://ollama.com)** on `http://127.0.0.1:11434`, not by local GGUF files in `backend/Models/`.

```
Browser → Login (7001) → RAG (7000) → Ollama (11434)
              ↑ optional LLM shim (8000/8010)
```

---

## Prerequisites

Install before you start:

- **Windows 10/11**
- **[Miniconda](https://docs.conda.io/en/latest/miniconda.html)** (or Anaconda)
- **[Git](https://git-scm.com/download/win)** (optional, for clones)
- **NVIDIA GPU + driver** (recommended; CPU-only is slower)
- **[Ollama for Windows](https://ollama.com)** — must be running while you use the app

**Hardware:** 16 GB RAM minimum; **6 GB VRAM** works if you use a small Ollama model (e.g. `qwen2.5:3b`).

---

## 1. One-time setup

Open **PowerShell** and go to the project root (adjust the path if yours differs):

```powershell
cd "c:\Users\a7med\Downloads\assistify-rag-project-final-rag-system\assistify-rag-project-final-rag-system"
```

### 1.1 Create the Conda environment

```powershell
conda env create -f environment_main.yml
```

This creates **`assistify_main`** with **Python 3.11** and most dependencies.

If the environment already exists:

```powershell
conda activate assistify_main
```

Verify:

```powershell
python --version
# Expected: Python 3.11.x
```

### 1.2 Extra Python packages (known gaps)

Still with `assistify_main` active:

```powershell
pip install itsdangerous authlib pdfplumber
pip install "setuptools<81"
```

`setuptools<81` avoids `pkg_resources` issues with **faster-whisper** / **ctranslate2** on some installs.

### 1.3 Environment file

```powershell
copy .env.example .env
```

Edit `.env` for local dev (recommended):

```env
ENVIRONMENT=development
OLLAMA_MODEL=qwen2.5:3b
KMP_DUPLICATE_LIB_OK=TRUE
```

For **6 GB VRAM**, prefer **`qwen2.5:3b`** over the default `qwen2.5:7b` in `config.py`.

If port **8000** is blocked on Windows, add:

```env
LLM_SERVER_PORT=8010
LLM_SERVER_URL=http://127.0.0.1:8010
```

### 1.4 Broken `graduation` virtualenv (if present)

If `graduation\pyvenv.cfg` points at another PC’s paths, **delete the whole `graduation` folder**. The launcher will use your active Conda Python instead.

### 1.5 Ollama model

Start Ollama (tray app or `ollama serve`), then:

```powershell
ollama pull qwen2.5:3b
```

Use the same tag as **`OLLAMA_MODEL`** in `.env` / `config.py`.

### 1.6 Knowledge base (sample documents)

Loads **10 built-in support snippets** into Chroma (no PDF required):

```powershell
conda activate assistify_main
python -m backend.load_documents
```

### 1.7 Login database (dev users)

```powershell
python Login_system\init_users_db.py
```

Creates `Login_system\users.db` with:

| Username | Password (dev) | Role |
|----------|----------------|------|
| `admin` | `admin` | admin |
| `employee` | `employee` | employee |

Passwords are stored as bcrypt hashes (see `Login_system/init_users_db.py`).

---

## 2. Run the project (every session)

### 2.1 Start Ollama

Ensure Ollama is running before starting Assistify.

### 2.2 Start all servers

```powershell
cd "c:\Users\a7med\Downloads\assistify-rag-project-final-rag-system\assistify-rag-project-final-rag-system"
conda activate assistify_main
$env:KMP_DUPLICATE_LIB_OK = "TRUE"
python scripts\project_start_server.py --kill-ports --llm-port 8010
```

- **`--kill-ports`** — frees ports if a previous run left listeners behind.
- **`--llm-port 8010`** — use when **8000** fails with “permission denied” on Windows; match `LLM_SERVER_URL` in `.env` if you set it.

**Ollama-only** (skip the FastAPI LLM process):

```powershell
python scripts\project_start_server.py --kill-ports --no-llm
```

Leave this window open while you use the app. Press **Ctrl+C** to stop all services.

### 2.3 Open the app

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:7001/login | **Main UI — start here** |
| http://127.0.0.1:7000/health | RAG health check |
| http://127.0.0.1:8010/internal/gpu-status | LLM shim status (if using port 8010) |

---

## 3. PDF and knowledge-base testing

**Default KB:** `python -m backend.load_documents` does **not** ingest PDFs; it loads text from code.

**PDF support** exists via the RAG server / admin upload flow and `backend/pdf_ingestion_rag.py`.

**Sample PDFs in the repo:**

- `tmp_test_pdfs\management_test.pdf`
- `tmp_test_pdfs\psychology_test.pdf`

Upload them through the **admin knowledge** UI (when logged in as admin), or place assets per your deployment docs and reindex.

**Good manual test questions** (after sample KB load):

- “How many days do I have to return a product?” → **30 days**
- “How do I reset my password?” → forgot-password / email steps
- “When is shipping free?” → **orders over $50**

---

## 4. Run tests (optional)

From project root with `assistify_main` active:

```powershell
$env:PYTHONUTF8 = "1"
python tests\test_system_integrity.py
python tests\test_edge_cases.py
python tests\test_toon.py
python tests\test_toon_integration.py
```

Skip **`tests\test_arabic_tts.py`** unless a TTS service is running on **port 5002** (Piper/XTTS).

Run most tests (excluding Arabic TTS):

```powershell
Get-ChildItem tests\test_*.py | Where-Object { $_.Name -ne "test_arabic_tts.py" } | ForEach-Object { python $_.FullName }
```

---

## 5. Troubleshooting

| Symptom | What to try |
|---------|-------------|
| `can't open file ... scripts\project_start_server.py` | `cd` into the **project root** first. |
| `$env:KMP_DUPLICATE_LIB_OK` error in **cmd** | Use PowerShell, or `set KMP_DUPLICATE_LIB_OK=TRUE` in cmd. |
| `No module named 'backend'` in tests | Run tests from repo root; use updated test files that set `sys.path` to parent of `tests/`. |
| LLM empty / connection errors | Start **Ollama**; run `ollama pull` for your model; check `OLLAMA_MODEL`. |
| Port **8000** permission denied | Use `--llm-port 8010` and set `LLM_SERVER_URL` accordingly. |
| OpenMP / crash with whisper + torch | `$env:KMP_DUPLICATE_LIB_OK = "TRUE"` (also in `.env`). |
| `passlib` / `bcrypt` version warning | Harmless if login works; optional: `pip install "bcrypt<4.1"`. |
| TTS warnings on **5002** | Optional; Piper not running. Chat can still work without voice output. |
| `graduation` venv broken | Delete `graduation\`; use Conda only. |

---

## 6. Project layout (short)

```
assistify-rag-project-final-rag-system/
├── backend/                 # RAG server, knowledge base, Ollama LLM shim
├── Login_system/            # Login server, users.db
├── frontend/                # Static HTML/JS
├── scripts/
│   └── project_start_server.py   # Recommended launcher
├── environment_main.yml     # Conda env definition
├── config.py                # Shared configuration
├── .env.example             # Copy to .env
└── docs/                    # Additional documentation
```

---

## 7. Quick reference (daily use)

```powershell
ollama pull qwen2.5:3b          # once per model
cd <project-root>
conda activate assistify_main
$env:KMP_DUPLICATE_LIB_OK = "TRUE"
python scripts\project_start_server.py --kill-ports --llm-port 8010
```

Then open **http://127.0.0.1:7001/login**.

For more detail, see `docs/PROJECT_BRIEFING.md`, `docs/ENV_SETUP_COMPLETE.md`, and `archived_pdfs/SETUP_REQUIREMENTS.md` (some GGUF steps there are outdated; this project uses **Ollama**).
