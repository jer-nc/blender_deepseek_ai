import bpy
# import all constants from the constants module
from .config import * 


class DeepSeekProperties:
    api_key: bpy.props.StringProperty(
        name="API Key",
        description="Your DeepSeek API Key",
        subtype='PASSWORD',
        default=""
    )
    
    api_url: bpy.props.StringProperty(
        name="API URL",
        description="DeepSeek API endpoint URL",
        default=DEFAULT_API_URL
    )
    
    model_name: bpy.props.StringProperty(
        name="Model",
        description="AI model to use",
        default=DEFAULT_MODEL
    )

    model_name_fix_errors: bpy.props.StringProperty(
        name="Model Fix Errors",
        description="AI model to use for error correction",
        default=DEFAULT_MODEL_FIX_ERRORS
    )
    
    max_tokens: bpy.props.IntProperty(
        name="Max Tokens",
        description="Maximum response length",
        default=DEFAULT_MAX_TOKENS,
        min=50,
        max=8000
    )
    
    temperature: bpy.props.FloatProperty(
        name="Temperature",
        description="Controls randomness (0.0 = deterministic, 1.0 = creative)",
        default=DEFAULT_TEMPERATURE,
        min=0.0,
        max=2.0,
        step=0.1
    )
    
    top_p: bpy.props.FloatProperty(
        name="Top P",
        description="Nucleus sampling probability threshold",
        default=DEFAULT_TOP_P,
        min=0.0,
        max=1.0,
        step=0.05
    )
    
    frequency_penalty: bpy.props.FloatProperty(
        name="Frequency Penalty",
        description="Penalize new tokens based on their frequency",
        default=DEFAULT_FREQUENCY_PENALTY,
        min=-2.0,
        max=2.0,
        step=0.1
    )
    
    presence_penalty: bpy.props.FloatProperty(
        name="Presence Penalty",
        description="Penalize new tokens based on their presence",
        default=DEFAULT_PRESENCE_PENALTY,
        min=-2.0,
        max=2.0,
        step=0.1
    )
    
    custom_prompt: bpy.props.StringProperty(
        name="Custom Prompt",
        description="Prompt template (use {code_context} for existing code)",
        default=DEFAULT_PROMPT,
    )
    
    error_prompt: bpy.props.StringProperty(
        name="Error Prompt",
        description="Prompt template for error correction (use {code}, {error}, {console_output})",
        default=DEFAULT_ERROR_PROMPT,
    )