from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.matches import router as matches_router
from app.api.routes.matching_workspace import router as matching_workspace_router
from kakimetch_common.config import get_allowed_origins

app = FastAPI(title="KakiMETch matching service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(matches_router)
app.include_router(matching_workspace_router)
