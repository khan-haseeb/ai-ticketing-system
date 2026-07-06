from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import settings
from app.api.users import router as users_router
from app.api.projects import router as projects_router
from app.api.tickets import router as tickets_router
from app.api.reports import router as reports_router
from app.api.chat import router as chat_router


app = FastAPI(title="Ticketing AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)
app.include_router(projects_router)
app.include_router(tickets_router)
app.include_router(reports_router)
app.include_router(chat_router)

# Serve the frontend — mount AFTER API routers so /api/* routes take priority
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/config")
async def get_config():
    return {"app_name": settings.app_name, "app_env": settings.app_env}