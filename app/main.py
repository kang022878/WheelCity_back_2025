# import os
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from app.db import connect, close
# from app.routers import health, places, reports

# from app.routers import ingest

# app = FastAPI(title="Wheel City API", version="0.1.0")

# origins = os.getenv("CORS_ORIGINS","").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_methods=["*"],
#     allow_headers=["*"],
#     allow_credentials=True,
# )

# @app.on_event("startup")
# async def on_startup():
#     await connect()

# @app.on_event("shutdown")
# async def on_shutdown():
#     await close()

# app.include_router(health.router, prefix="/health", tags=["health"])
# app.include_router(places.router, prefix="/places", tags=["places"])
# app.include_router(reports.router, prefix="/reports", tags=["reports"])

# app.include_router(ingest.router,  prefix="/ingest", tags=["ingest"])

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import connect, close
from app.routers import health, places, reports
from app.routers import ingest
from app.routers import auth

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
    await connect(app)   # ✅ app을 넘겨서 app.state.db에 주입
    from app.db import db as gdb
    app.state.db = gdb

@app.on_event("shutdown")
async def on_shutdown():
    await close()     # ✅ app에서 꺼내 닫기

app.include_router(health.router,  prefix="/health",  tags=["health"])
app.include_router(places.router,  prefix="/places",  tags=["places"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(ingest.router,  prefix="/ingest",  tags=["ingest"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
