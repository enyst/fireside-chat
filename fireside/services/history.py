# fireside/services/history.py

"""
Handles saving and retrieving chat conversation history.
V1: Uses simple JSON files stored on the filesystem.
"""

import os
import json
import uuid
from datetime import datetime
import logging
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
HISTORY_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'history') # Store history outside 'fireside' package
# Ensure the history directory exists
os.makedirs(HISTORY_DIR, exist_ok=True)

# --- Data Structures ---
# Structure of a single turn in a conversation
Turn = Dict[str, str] # e.g., {"role": "user", "text": "Hello"} or {"role": "model", "text": "Hi there!"}
# Structure of a conversation file
Conversation = Dict[str, List[Turn]] # e.g., {"messages": [...]}

# --- Core Functionality ---

def get_conversation_path(conversation_id: str) -> str:
    """Constructs the full path for a conversation file."""
    # Basic sanitization to prevent path traversal
    safe_id = "".join(c for c in conversation_id if c.isalnum() or c in ['-', '_'])
    if not safe_id:
        raise ValueError("Invalid conversation ID format.")
    return os.path.join(HISTORY_DIR, f"{safe_id}.json")

def save_message(conversation_id: Optional[str], user_prompt: str, model_response: str) -> str:
    """
    Saves a user prompt and model response to a conversation history file.
    Creates a new conversation file if conversation_id is None.

    Args:
        conversation_id: The ID of the existing conversation, or None to start a new one.
        user_prompt: The text of the user's prompt.
        model_response: The text of the model's response.

    Returns:
        The conversation ID (new or existing).
    """
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())
        conversation_data: Conversation = {"messages": []}
        logger.info(f"Starting new conversation with ID: {conversation_id}")
    else:
        try:
            conversation_data = load_conversation(conversation_id)
            if conversation_data is None: # Handle case where ID is provided but file doesn't exist
                 logger.warning(f"Conversation ID {conversation_id} provided, but file not found. Creating new.")
                 conversation_data = {"messages": []}

        except Exception as e:
            logger.error(f"Error loading conversation {conversation_id} for saving: {e}", exc_info=True)
            # Decide on recovery strategy: maybe create new anyway? Or raise error?
            # For simplicity, let's create a new one if loading fails badly.
            conversation_id = str(uuid.uuid4())
            conversation_data = {"messages": []}
            logger.info(f"Started new conversation {conversation_id} due to load error.")


    # Append new turns
    conversation_data["messages"].append({"role": "user", "text": user_prompt})
    conversation_data["messages"].append({"role": "model", "text": model_response})

    # Save back to file
    try:
        filepath = get_conversation_path(conversation_id)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(conversation_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved message turn to conversation: {conversation_id}")
        return conversation_id
    except (IOError, ValueError, TypeError) as e:
        logger.error(f"Error saving conversation {conversation_id} to {filepath}: {e}", exc_info=True)
        raise  # Re-raise the exception to be handled by the API layer

def load_conversation(conversation_id: str) -> Optional[Conversation]:
    """
    Loads a conversation history from its JSON file.

    Args:
        conversation_id: The ID of the conversation to load.

    Returns:
        The conversation data as a dictionary, or None if the file doesn't exist or is invalid.
    """
    try:
        filepath = get_conversation_path(conversation_id)
        if not os.path.exists(filepath):
            logger.warning(f"Conversation file not found: {filepath}")
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Basic validation
            if isinstance(data, dict) and "messages" in data and isinstance(data["messages"], list):
                 logger.info(f"Loaded conversation: {conversation_id}")
                 return data
            else:
                 logger.error(f"Invalid format in conversation file: {filepath}")
                 return None # Or raise an error?
    except (IOError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error loading conversation {conversation_id} from {filepath}: {e}", exc_info=True)
        return None # Or raise? Returning None might be safer for API stability.

def list_conversations() -> List[Dict[str, str]]:
    """
    Lists available conversations based on the files in the history directory.

    Returns:
        A list of dictionaries, each containing 'id' and 'summary' (first message).
        Returns an empty list if the directory doesn't exist or on error.
    """
    if not os.path.isdir(HISTORY_DIR):
        logger.warning(f"History directory not found: {HISTORY_DIR}")
        return []

    conversations = []
    try:
        for filename in os.listdir(HISTORY_DIR):
            if filename.endswith(".json"):
                conversation_id = filename[:-5] # Remove .json extension
                filepath = os.path.join(HISTORY_DIR, filename)
                summary = "Conversation" # Default summary
                timestamp = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M')

                # Try to load the first message as a summary
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data and "messages" in data and data["messages"]:
                            first_message = data["messages"][0]
                            if first_message and "text" in first_message:
                                summary = first_message["text"][:80] + ('...' if len(first_message["text"]) > 80 else '') # Truncate long summaries
                except Exception as e:
                    logger.warning(f"Could not read summary from {filename}: {e}")
                    # Keep default summary

                conversations.append({
                    "id": conversation_id,
                    "summary": summary,
                    "last_modified": timestamp
                })

        # Sort by last modified time, newest first
        conversations.sort(key=lambda x: x["last_modified"], reverse=True)
        logger.info(f"Found {len(conversations)} conversations.")
        return conversations

    except OSError as e:
        logger.error(f"Error listing conversations in {HISTORY_DIR}: {e}", exc_info=True)
        return [] # Return empty list on error
