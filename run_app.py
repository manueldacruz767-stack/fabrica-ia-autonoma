import os

import uvicorn

from app import db

if __name__ == "__main__":
    db.inicializar()
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HIS_HOST", "127.0.0.1"),
        port=int(os.getenv("HIS_PORT", "8000")),
        reload=False,
    )
