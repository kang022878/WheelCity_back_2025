import os
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.db import connect, close, db as mongo_db
from app.routers import health, reviews, shops, users


app = FastAPI(title="Wheel City API", version="0.1.0")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and log them."""
    print(f"[GLOBAL ERROR] Unhandled exception: {type(exc).__name__}: {exc}")
    print(f"[GLOBAL ERROR] Path: {request.url.path}")
    traceback_str = traceback.format_exc()
    print(f"[GLOBAL ERROR] Traceback:\n{traceback_str}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal server error: {str(exc)}",
            "type": type(exc).__name__
        }
    )

origins = os.getenv("CORS_ORIGINS","").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

@app.on_event("startup")
async def on_startup():
    await connect()
    app.state.db = mongo_db

@app.on_event("shutdown")
async def on_shutdown():
    await close()

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(shops.router, prefix="/shops", tags=["shops"])
app.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
