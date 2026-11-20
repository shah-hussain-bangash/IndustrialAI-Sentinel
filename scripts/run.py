"""Serve the built application from a single local origin."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=False)
if not (ROOT / "dist" / "index.html").exists():
    raise SystemExit("Build the frontend first: pnpm install && pnpm build. See README.md.")
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8127")))
