import os
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from the .env file automatically
load_dotenv()

# Setup professional logging
logger = logging.getLogger(__name__)

# Fetch the API key from system memory safely
API_KEY = os.getenv("GEMINI_API_KEY")

def is_ai_configured() -> bool:
    """
    Checks if the Gemini API key is present and configured.
    Prevents crashing the app if the user hasn't supplied a key yet.
    """
    if not API_KEY or API_KEY == "your_actual_api_key_here":
        return False
    return True

# Initialize the modern unified Gemini Client
if is_ai_configured():
    client = genai.Client(api_key=API_KEY)
    logger.info("Google Gen AI SDK successfully configured.")
else:
    client = None
    logger.warning("Gemini API key is missing or default. AI features will run in sandbox mode.")

def _call_gemini(prompt: str, system_instruction: Optional[str] = None) -> str:
    """
    Internal helper function that safely handles the direct network connection to Gemini.
    """
    if not is_ai_configured() or client is None:
        return "[AI Sandbox Mode] Set up your real GEMINI_API_KEY to see live responses!"

    try:
        # Build the generation configuration block if system instructions exist
        config = None
        if system_instruction:
            config = types.GenerateContentConfig(system_instruction=system_instruction)

        # Using the stable production flash engine
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API execution error: {e}")
        return "Error: Unable to process AI request at this time."

def generate_smart_replies(message_content: str) -> str:
    """
    Analyzes a message and generates 3 short, context-aware reply suggestions.
    """
    system_prompt = (
        "You are an assistant embedded in a secure chat app. Analyze the user's incoming message "
        "and generate exactly 3 short, contextually accurate, conversational reply options. "
        "Format the output strictly as a single line separated by vertical pipes, like this: "
        "Option One | Option Two | Option Three. Do not add introductory text or explanations."
    )
    return _call_gemini(prompt=message_content, system_instruction=system_prompt)

def correct_grammar(message_content: str) -> str:
    """
    Fixes grammar and spelling errors instantly while maintaining the user's original intent.
    """
    system_prompt = (
        "You are an expert editor. Clean up any grammar, spelling, or punctuation issues "
        "in the text provided. Only output the beautifully corrected sentence. Do not add annotations, "
        "quotes, or explanations."
    )
    return _call_gemini(prompt=message_content, system_instruction=system_prompt)

def translate_text(message_content: str, target_language: str) -> str:
    """
    Translates text clearly into any specified language.
    """
    system_prompt = (
        f"You are a fluent multilingual translator. Translate the incoming text clearly into {target_language}. "
        "Maintain a natural, human tone. Output only the translated result without meta-commentary."
    )
    return _call_gemini(prompt=message_content, system_instruction=system_prompt)