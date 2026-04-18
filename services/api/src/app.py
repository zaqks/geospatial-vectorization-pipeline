from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
# from .db import init_db
from .client.routes import router

app = FastAPI(
    title="GeoVect API",
    description="GeoRef + Vectorization API",
    version="1.0.0"
)


# @app.on_event("startup")
# def on_startup() -> None:
#     init_db()

# CORS Middleware
# In production, replace ["*"] with the actual frontend domain(s)
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


@app.get("/media/{filename}")
async def serve_media(filename: str):
    """
    Serve media files from the static directory.
    """
    media_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", filename)
    return FileResponse(media_path)


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify the service is running.
    """
    return {"status": "ok", "message": "trader says hi"}
