import os
from pathlib import Path
from fastapi import Header, HTTPException
from dotenv import load_dotenv

# Load .env file (same way as db.py does it)
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
print(f"[DEPS] Loading .env from: {env_path}", flush=True)
print(f"[DEPS] .env file exists: {env_path.exists()}", flush=True)
if env_path.exists():
    print(f"[DEPS] .env file size: {env_path.stat().st_size} bytes", flush=True)
load_dotenv(dotenv_path=env_path)

# Try both variable names for compatibility
API_KEY = os.getenv("API_KEY_INTERNAL") or os.getenv("INTERNAL_API_KEY")
if API_KEY:
    print(f"[DEPS] Found API key: {API_KEY[:10]}...", flush=True)
else:
    print(f"[DEPS] API_KEY_INTERNAL from env: {os.getenv('API_KEY_INTERNAL')}", flush=True)
    print(f"[DEPS] INTERNAL_API_KEY from env: {os.getenv('INTERNAL_API_KEY')}", flush=True)
    print(f"[DEPS] All env vars with 'API': {[k for k in os.environ.keys() if 'API' in k.upper()]}", flush=True)


async def verify_internal(x_api_key: str = Header(None, alias="X-API-Key")):
    """
    Verify internal API key from X-API-Key header.
    The header name is explicitly set to 'X-API-Key'.
    """
    print(f"[AUTH] Received header X-API-Key: {x_api_key[:10] if x_api_key else None}...", flush=True)
    print(f"[AUTH] Expected API_KEY from env: {API_KEY[:10] if API_KEY else None}...", flush=True)
    print(f"[AUTH] API_KEY is None: {API_KEY is None}", flush=True)
    
    if not API_KEY:
        print("[AUTH ERROR] API_KEY_INTERNAL is not set in environment!", flush=True)
        raise HTTPException(status_code=500, detail="API key not configured on server")
    
    if not x_api_key:
        print("[AUTH ERROR] X-API-Key header is missing", flush=True)
        raise HTTPException(status_code=401, detail="Unauthorized: X-API-Key header required")
    
    if x_api_key != API_KEY:
        print(f"[AUTH ERROR] API key mismatch! Received: {x_api_key[:10]}..., Expected: {API_KEY[:10]}...", flush=True)
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API key")
    
    print("[AUTH] API key verified successfully", flush=True)
