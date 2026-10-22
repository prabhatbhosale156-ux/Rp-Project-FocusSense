import os
import uvicorn
from main import app

if __name__ == "__main__":
    host = os.environ.get("FOCUSSENSE_HOST", "127.0.0.1")
    port = int(os.environ.get("FOCUSSENSE_PORT", "8000"))
    uvicorn.run(app, host=host, port=port, reload=False, access_log=True)
