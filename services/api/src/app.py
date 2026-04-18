from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .client.routes import router as client_router
from .media.routes import router as media_router

app = FastAPI(
    title="GeoVect API",
    description="GeoRef + Vectorization API",
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

# Include routers
app.include_router(client_router)
app.include_router(media_router)


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify the service is running.
    """
    return {"status": "ok", "message": "wilsooonnnnnnnn"}
