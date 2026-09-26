from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.trips import router as trips_router
from app.api.routes.schedule import router as schedule_router
from kakimetch_common.config import get_allowed_origins

app = FastAPI(title="KakiMETch scheduling service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(trips_router)
app.include_router(schedule_router)
