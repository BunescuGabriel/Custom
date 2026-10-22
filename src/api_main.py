import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.backend.app:app",
        host=os.environ.get("API_HOST", "127.0.0.1"),
        port=int(os.environ.get("API_PORT", "8000")),
        reload=True,
    )
