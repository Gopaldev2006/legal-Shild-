import sys
import os
import uvicorn

# Add backend folder to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

if __name__ == "__main__":
    print("Starting Secure Legal AI Backend Server...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
