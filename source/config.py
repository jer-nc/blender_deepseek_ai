DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_MODEL_FIX_ERRORS = "deepseek-chat"
DEFAULT_MAX_TOKENS = 8000
DEFAULT_TEMPERATURE = 0.5
DEFAULT_TOP_P = 0.95
DEFAULT_FREQUENCY_PENALTY = 0.0
DEFAULT_PRESENCE_PENALTY = 0.0
DEFAULT_PROMPT = (
    "Continue the Blender Python code STRICTLY FOLLOWING:\n"
    "1. ONLY valid Python code WITHOUT markdown\n"
    "2. Use # comments ONLY for brief technical notes\n"
    "3. Maintain the existing code style\n"
    "4. Respond EXCLUSIVELY with the new necessary code\n\n"
    "5. Feel free to completely REWRITE the code if the user's request requires a different approach\n\n"
    "Current context:\n"
    "'''\n"
    "{code_context}\n"
    "'''\n\n"
    "'''\n"
    "{scene_context}\n"
    "'''\n\n"
    "New request: "
)
DEFAULT_ERROR_PROMPT = (
    "Fix this Blender Python code based on the error:\n"
    "Error: {error}\n"
    "Console output:\n'''\n{console_output}\n'''\n"
    "Original code:\n'''\n{code}\n'''\n"
    "Instructions:\n"
    "1. Provide ONLY the corrected code\n"
    "2. Add comments ONLY to the corrected lines of code\n"
    "3. Maintain the original code style\n"
)