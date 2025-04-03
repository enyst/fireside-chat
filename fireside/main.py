from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Determine the absolute path to the 'static' directory relative to this file
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
# Determine the path to the index.html file
index_html_path = os.path.join(static_dir, 'index.html')

app = FastAPI()

# Mount the static directory to serve files like CSS, JS, images
# Note: App Engine's 'static_dir' handler in app.yaml often handles this,
# but mounting it here is good practice for local testing and clarity.
# We use a relative path from the project root for the source path.
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    """Serves the main index.html file."""
    # Check if index.html exists before serving
    if os.path.exists(index_html_path):
        return FileResponse(index_html_path)
    else:
        return {"message": "index.html not found"}, 404

@app.get("/hello")
async def hello():
    """A simple API endpoint."""
    return {"message": "Hello from FastAPI!"}

