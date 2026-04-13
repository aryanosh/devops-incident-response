import subprocess
import time
import sys
import os

def main():
    print("Starting FastAPI backend...")
    fastapi_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait a bit for backend to start
    time.sleep(3)
    
    print("Starting Gradio frontend...")
    env = os.environ.copy()
    env["API_URL"] = "http://localhost:8000"
    
    gradio_process = subprocess.Popen(
        [sys.executable, "gradio_app.py"],
        env=env
    )
    
    try:
        gradio_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        fastapi_process.terminate()
        gradio_process.terminate()

if __name__ == "__main__":
    main()
