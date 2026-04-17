from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from .routes import router

app = FastAPI(
    title="Trading API",
    description="API for the Trading Platform",
    version="1.0.0"
)

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

# Mount static files
static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Include routers
app.include_router(router)


@app.get("/")
async def root():
    """
    Serve the index.html template.
    """
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "index.html")
    return FileResponse(template_path)


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify the service is running.
    """
    return {"status": "ok", "message": "trader says hi"}
