import logging
import os
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Import services
from .services import vertex_ai, history

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Determine the absolute path to the 'static' directory relative to this file
# Note: Using relative paths from the project root is often more robust for deployment
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
# Determine the path to the index.html file
index_html_path = os.path.join(static_dir, 'index.html')


# --- Pydantic Models ---

class ChatRequest(BaseModel):
    prompt: str
    conversation_id: Optional[str] = None
    settings_override: Optional[Dict] = None # e.g., {"temperature": 0.5}

class ChatResponse(BaseModel):
    response: str
    conversation_id: str

class HistorySummary(BaseModel):
    id: str
    summary: str
    last_modified: str # Keep as string for simplicity

class HistoryDetail(BaseModel):
    role: str # 'user' or 'model'
    text: str


# --- FastAPI App ---

app = FastAPI(title="Fireside Chat API")

# Mount the static directory to serve files like CSS, JS
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
        # Use JSONResponse for proper error handling if preferred
        # return JSONResponse(content={"message": "index.html not found"}, status_code=404)
        raise HTTPException(status_code=404, detail="index.html not found")


# --- API Endpoints ---

@app.post("/api/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    """Handles a chat request, interacts with the LLM, and saves history."""
    logger.info(f"Received chat request for conversation_id: {request.conversation_id}")

    conversation_history_turns = []
    if request.conversation_id:
        # Load existing conversation history
        loaded_conversation = history.load_conversation(request.conversation_id)
        if loaded_conversation:
            conversation_history_turns = loaded_conversation.get("messages", [])
            # Convert history format if needed for the LLM service
            # Assuming vertex_ai.generate_chat_response expects [{"role": ..., "parts": [{"text": ...}]}]
            # This might need adjustment based on vertex_ai.py implementation details
            llm_history = []
            for turn in conversation_history_turns:
                 if turn.get("role") and turn.get("text"):
                     llm_history.append({"role": turn["role"], "parts": [{"text": turn["text"]}]})
                 else:
                     logger.warning(f"Skipping invalid turn in history: {turn}")

        else:
            logger.warning(f"Conversation ID {request.conversation_id} provided but not found. Starting new.")
            request.conversation_id = None # Treat as new conversation

    try:
        # Call the LLM service
        model_response_text = vertex_ai.generate_chat_response(
            prompt=request.prompt,
            conversation_history=llm_history if request.conversation_id else None, # Pass history only if ID exists
            settings_override=request.settings_override
        )

        # Check for errors from the LLM service
        if model_response_text.startswith("Error:"):
             raise HTTPException(status_code=500, detail=model_response_text)


        # Save the new turn to history
        # This returns the conversation ID (either existing or newly generated)
        updated_conversation_id = history.save_message(
            conversation_id=request.conversation_id,
            user_prompt=request.prompt,
            model_response=model_response_text
        )

        return ChatResponse(response=model_response_text, conversation_id=updated_conversation_id)

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions directly
        raise http_exc
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")


@app.get("/api/history", response_model=List[HistorySummary])
async def get_history_list():
    """Retrieves a list of conversation summaries."""
    try:
        summaries = history.list_conversations()
        # Convert dicts to HistorySummary objects (Pydantic handles this with response_model)
        return summaries
    except Exception as e:
        logger.error(f"Error retrieving history list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve conversation history list.")


@app.get("/api/history/{conversation_id}", response_model=List[HistoryDetail])
async def get_conversation_details(conversation_id: str):
    """Retrieves the full message history for a specific conversation."""
    logger.info(f"Requesting history for conversation_id: {conversation_id}")
    try:
        conversation_data = history.load_conversation(conversation_id)
        if conversation_data is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        # Extract messages and convert to HistoryDetail objects (Pydantic handles this)
        messages = conversation_data.get("messages", [])
        return messages # Assuming messages are already in {"role": ..., "text": ...} format

    except ValueError as ve: # Catch invalid ID format from get_conversation_path
         logger.warning(f"Invalid conversation ID format requested: {conversation_id} - {ve}")
         raise HTTPException(status_code=400, detail="Invalid conversation ID format.")
    except Exception as e:
        logger.error(f"Error retrieving conversation details for {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve conversation details.")


# @app.get("/api/settings")
# async def get_settings():
#     # Return non-sensitive settings only
#     # Example: return {"model_id": vertex_ai.MODEL_ID, "project_id": vertex_ai.PROJECT_ID}
#     pass

# @app.post("/api/settings")
# async def update_settings(settings: Dict):
#     # Handle updates for settings if needed
#     pass
