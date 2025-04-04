# fireside/services/vertex_ai.py (Refactored for google-generativeai targeting Vertex AI)

"""
Handles interaction with Google Vertex AI Gemini models using the google-generativeai SDK
configured for Vertex AI endpoints and ADC authentication.
"""

import os
import google.generativeai as genai
import logging
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
# The google-generativeai SDK will automatically configure for Vertex AI
# if GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, and GOOGLE_GENAI_USE_VERTEXAI=True
# are set in the environment (e.g., via app.yaml).

# We still allow overriding the default model via an environment variable.
DEFAULT_MODEL_ID = os.environ.get("VERTEX_MODEL_ID", "gemini-1.5-flash-latest") # Keep this name consistent if used in app.yaml override

# --- Initialization ---
# No explicit genai.init() needed here when relying on environment variables for Vertex AI config.
# The SDK handles initialization automatically upon first use (e.g., when GenerativeModel is called).
logger.info("Google AI SDK will attempt auto-configuration for Vertex AI based on environment variables.")


# --- Core Functionality ---

def generate_chat_response(prompt: str, conversation_history: Optional[List[Dict]] = None, settings_override: Optional[Dict] = None) -> str:
    """
    Sends a prompt to the configured Vertex AI Gemini model via the google-generativeai SDK.

    Args:
        prompt: The user's input prompt.
        conversation_history: A list of previous turns in the conversation, if any.
                              Expected format: [{"role": "user", "parts": ["text"]}, {"role": "model", "parts": ["text"]}]
        settings_override: Optional dictionary to override default model parameters
                           (e.g., model_id, temperature, max_output_tokens).

    Returns:
        The text response from the model.
        Returns an error message string if the API call fails or SDK is not configured via environment.
    """
    # No need to check PROJECT_ID/LOCATION here, SDK handles it based on env vars.
    # If env vars are missing, the model call below will likely raise an error.

    try:
        # Determine model and generation config
        current_model_id = DEFAULT_MODEL_ID # Start with default
        gen_config_overrides = {}
        if settings_override:
            current_model_id = settings_override.get("model_id", DEFAULT_MODEL_ID)
            if "temperature" in settings_override:
                gen_config_overrides["temperature"] = settings_override["temperature"]
            if "max_output_tokens" in settings_override:
                gen_config_overrides["max_output_tokens"] = settings_override["max_output_tokens"]
            # Add other supported parameters (top_p, top_k) if needed

        # When using Vertex AI backend, model names might need the 'models/' prefix,
        # but genai library often handles this. Test if prefix is needed.
        # Example: model = genai.GenerativeModel(f"models/{current_model_id}")
        model = genai.GenerativeModel(current_model_id)

        # Format history for the google-genai library
        formatted_history = []
        if conversation_history:
            for turn in conversation_history:
                role = turn.get("role")
                parts_list = turn.get("parts", [])
                text_content = ""
                if parts_list and isinstance(parts_list, list) and len(parts_list) > 0:
                     first_part = parts_list[0]
                     if isinstance(first_part, dict) and "text" in first_part:
                         text_content = first_part["text"]
                     elif isinstance(first_part, str):
                         text_content = first_part

                if role and text_content:
                     # Ensure role is 'user' or 'model' as expected by genai
                     valid_role = "model" if role.lower() == "model" else "user"
                     formatted_history.append({"role": valid_role, "parts": [text_content]})
                else:
                     logger.warning(f"Skipping invalid history turn for google-genai: {turn}")


        logger.info(f"Sending request to Vertex AI model: {current_model_id} via genai SDK with history length: {len(formatted_history)}")

        # Start chat session if history exists, otherwise generate directly
        if formatted_history:
            chat_session = model.start_chat(history=formatted_history)
            response = chat_session.send_message(prompt, generation_config=genai.types.GenerationConfig(**gen_config_overrides) if gen_config_overrides else None)
        else:
            response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(**gen_config_overrides) if gen_config_overrides else None)


        # --- Response Parsing (same as before for genai) ---
        if response.parts:
             model_response = "".join(part.text for part in response.parts)
             logger.info("Successfully received response from Vertex AI (via genai SDK).")
             return model_response
        elif response.candidates and response.candidates[0].content.parts:
             model_response = "".join(part.text for part in response.candidates[0].content.parts)
             logger.info("Successfully received response from Vertex AI (via genai SDK candidates).")
             return model_response
        else:
             try:
                 _ = response.text # Check for blocks
             except ValueError as ve:
                 logger.error(f"Response blocked or invalid: {ve}. Full response: {response}")
                 return f"Error: Model response blocked or invalid. Reason: {ve}"
             except Exception as e_text:
                 logger.error(f"Could not extract text from response. Error: {e_text}. Response: {response}")

             logger.error(f"Could not extract text response from Vertex AI (via genai SDK): {response}")
             return "Error: Could not parse the model's response (empty or unexpected format)."


    except Exception as e:
        logger.error(f"Error calling Vertex AI (via google-generativeai): {e}", exc_info=True)
        return f"Error communicating with the AI model: {e}"
