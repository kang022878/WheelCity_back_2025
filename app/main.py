import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import connect, close
from app.routers import health, places, reports, accessibility

app = FastAPI(title="Wheel City API", version="0.1.0")

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
    await connect()                # app 인자 제거
    from app.db import db as gdb
    app.state.db = gdb 

@app.on_event("shutdown")
async def on_shutdown():
    await close()

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(places.router, prefix="/places", tags=["places"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])

app.include_router(accessibility.router, tags=["accessibility"])
