import uvicorn
import os
import logging


if __name__ == "__main__":
    # logging.getLogger("sqlalchemy").setLevel(logging.ERROR)

    uvicorn.run(
        "src.app:app",
        reload=os.getenv("RELOAD") != "false",
        port=8000,
        host="0.0.0.0",
        # workers=4,
    )
