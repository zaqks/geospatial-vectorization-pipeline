from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify the service is running.
    """
    return {"status": "ok", "message": "trader says hi"}


 


[app.include_router(_) for _ in []]
