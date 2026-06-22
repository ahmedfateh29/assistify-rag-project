# Canonical project location

Use **one** working copy of Assistify on this machine.

## Active project (code + data)

```
C:\Users\a7med\Downloads\assistify-rag-project-final-rag-system\assistify-rag-project-final-rag-system
```

- Run all commands from this folder (two nested `assistify-rag-project-final-rag-system` segments only).
- Git remote: `https://github.com/ahmedfateh29/assistify-rag-project.git`

## Archive / backup copy (do not run from here)

```
D:\Grad_Project\assistify-rag-project-main
```

Large files (`backend\Models`, etc.) may exist here from an older layout. The C: project can symlink or copy Whisper caches from D: if needed; do not maintain two live databases.

## After moving large folders

1. Keep `backend\Models`, `backend/chroma_db_v3`, and `backend/assets` under the C: project root, **or** set `WHISPER_MODEL_PATH`, `CHROMA_DB_PATH`, and `ASSETS_DIR` in `.env`.
2. Run `python scripts/preflight_check.py` before starting servers.
3. If sqlite3 fails with "Application Control policy", see [WINDOWS_TROUBLESHOOTING.md](WINDOWS_TROUBLESHOOTING.md).
