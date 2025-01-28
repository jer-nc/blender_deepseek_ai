import bpy
import requests
import re
from bpy.props import StringProperty, IntProperty, FloatProperty
from bpy.types import Operator, AddonPreferences, TEXT_MT_editor_menus
import sys
import io
import traceback

# Default configuration
DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_MAX_TOKENS = 4000
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.95
DEFAULT_FREQUENCY_PENALTY = 0.0
DEFAULT_PRESENCE_PENALTY = 0.0
DEFAULT_PROMPT = (
    "Continue the Blender Python code STRICTLY FOLLOWING:\n"
    "1. ONLY valid Python code WITHOUT markdown\n"
    "2. Use # comments ONLY for brief technical notes\n"
    "3. Maintain the existing code style\n"
    "4. Respond EXCLUSIVELY with the new necessary code\n\n"
    "Current context:\n"
    "'''\n"
    "{code_context}\n"
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

class DeepSeekPreferences(AddonPreferences):
    bl_idname = __name__

   
    api_key: StringProperty(
        name="API Key",
        description="Your DeepSeek API Key",
        subtype='PASSWORD',
        default=""
    )
    
    api_url: StringProperty(
        name="API URL",
        description="DeepSeek API endpoint URL",
        default=DEFAULT_API_URL
    )
    
    model_name: StringProperty(
        name="Model",
        description="AI model to use",
        default=DEFAULT_MODEL
    )
    
    max_tokens: IntProperty(
        name="Max Tokens",
        description="Maximum response length",
        default=DEFAULT_MAX_TOKENS,
        min=50,
        max=8000
    )
    
    temperature: FloatProperty(
        name="Temperature",
        description="Controls randomness (0.0 = deterministic, 1.0 = creative)",
        default=DEFAULT_TEMPERATURE,
        min=0.0,
        max=2.0,
        step=0.1
    )
    
    top_p: FloatProperty(
        name="Top P",
        description="Nucleus sampling probability threshold",
        default=DEFAULT_TOP_P,
        min=0.0,
        max=1.0,
        step=0.05
    )
    
    frequency_penalty: FloatProperty(
        name="Frequency Penalty",
        description="Penalize new tokens based on their frequency",
        default=DEFAULT_FREQUENCY_PENALTY,
        min=-2.0,
        max=2.0,
        step=0.1
    )
    
    presence_penalty: FloatProperty(
        name="Presence Penalty",
        description="Penalize new tokens based on their presence",
        default=DEFAULT_PRESENCE_PENALTY,
        min=-2.0,
        max=2.0,
        step=0.1
    )
    
    custom_prompt: StringProperty(
        name="Custom Prompt",
        description="Prompt template (use {code_context} for existing code)",
        default=DEFAULT_PROMPT,
    )

    error_prompt: StringProperty(
        name="Error Prompt",
        description="Prompt template for error correction (use {code}, {error}, {console_output})",
        default=DEFAULT_ERROR_PROMPT,
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="API Configuration:")
        layout.prop(self, "api_key")
        layout.prop(self, "api_url")
        layout.prop(self, "model_name")
        
        layout.separator()
        layout.label(text="Generation Parameters:")
        layout.prop(self, "max_tokens")
        layout.prop(self, "temperature")
        layout.prop(self, "top_p")
        layout.prop(self, "frequency_penalty")
        layout.prop(self, "presence_penalty")
        
        layout.separator()
        layout.label(text="Prompt Configuration:")
        layout.prop(self, "custom_prompt")

        layout.separator()
        layout.label(text="Error Correction Prompt:")
        layout.prop(self, "error_prompt")

class DEEPSEEK_OT_FixErrors(Operator):
    bl_idname = "text.deepseek_fix_errors"
    bl_label = "DeepSeek Fix Errors"
    bl_description = "Fix Python errors using AI, this will execute the code and send the error to DeepSeek"
    
    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        text_block = context.space_data.text
        
        # Capture the code and execute it
        code = text_block.as_string()
        old_stdout, old_stderr = sys.stdout, sys.stderr
        output_buffer = io.StringIO()
        
        sys.stdout = sys.stderr = output_buffer
        error_occurred = False
        error_msg = ""
        
        try:
            namespace = {'__name__': '__main__', 'bpy': bpy}
            exec(code, namespace)
        except Exception as e:
            error_occurred = True
            error_msg = str(e)
            traceback.print_exc(file=output_buffer)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
        
        console_output = output_buffer.getvalue()
        output_buffer.close()
        
        if not error_occurred:
            self.report({'INFO'}, "Errors not detected")
            return {'FINISHED'}
        
        # Send the error to DeepSeek
        prompt = prefs.error_prompt.format(
            code=code,
            error=error_msg,
            console_output=console_output
        )
        
        try:
            response = requests.post(
                prefs.api_url,
                headers={"Authorization": f"Bearer {prefs.api_key}"},
                json={
                    "model": prefs.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": prefs.temperature,
                    "top_p": prefs.top_p,
                    "frequency_penalty": prefs.frequency_penalty,
                    "presence_penalty": prefs.presence_penalty,
                    "stream": False
                },
                timeout=120
            )
            
            if response.status_code == 200:
                corrected_code = self.clean_response(response.json()["choices"][0]["message"]["content"])
                text_block.clear()
                text_block.write(corrected_code)
                self.report({'INFO'}, "Errors fixed successfully")
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
        
        return {'FINISHED'}
    
    def clean_response(self, response):
        return re.sub(r'```\w*\s*', '', response).strip()
    

class DEEPSEEK_OT_AutoComplete(Operator):
    bl_idname = "text.deepseek_autocomplete"
    bl_label = "DeepSeek Autocomplete"
    bl_description = "Generate code suggestions using AI"
    
    _timer = None
    original_text = ""

    def get_code_context(self, context):
        text_block = context.space_data.text
        current_line_index = text_block.current_line_index
        cursor_idx = text_block.current_character
        
        full_context = []
        for line in text_block.lines[:current_line_index]:
            full_context.append(line.body)
        
        if text_block.lines:
            current_line = text_block.lines[current_line_index].body
            full_context.append(current_line[:cursor_idx])
        
        return '\n'.join(full_context)

    def clean_response(self, response):
        # Remove any trailing whitespace 
        response = re.sub(r'```\w*\s*', '', response)
      
        response = re.sub(r'\n{3,}', '\n\n', response) 
        return response.strip()

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        
        if not prefs.api_key:
            self.report({'ERROR'}, "API Key not configured")
            return {'CANCELLED'}

        code_context = self.get_code_context(context)
        full_prompt = prefs.custom_prompt.format(code_context=code_context)
        
        try:
            print("\n[DeepSeek] Processing request...")
            response = requests.post(
                prefs.api_url,
                headers={
                    "Authorization": f"Bearer {prefs.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": prefs.model_name,
                    "messages": [{
                        "role": "user",
                        "content": full_prompt
                    }],
                    "max_tokens": prefs.max_tokens,
                    "temperature": prefs.temperature,
                    "top_p": prefs.top_p,
                    "frequency_penalty": prefs.frequency_penalty,
                    "presence_penalty": prefs.presence_penalty,
                    "stream": False
                },
                timeout=120
            )

            if response.status_code == 200:
                suggestion = response.json()["choices"][0]["message"]["content"]
                cleaned_suggestion = self.clean_response(suggestion)
                
                text_block = context.space_data.text
                
                if text_block.current_line.body.strip() != "":
                    text_block.write("\n\n")
                
                text_block.write(cleaned_suggestion)
                

                text_block.current_line_index = len(text_block.lines) - 1
                text_block.current_character = len(text_block.current_line.body)
            else:
                error_msg = f"API Error: {response.text[:100]}..." if len(response.text) > 100 else response.text
                self.report({'ERROR'}, error_msg)
                print(f"[DeepSeek] {error_msg}")
                
        except Exception as e:
            error_msg = f"Connection Error: {str(e)}"
            self.report({'ERROR'}, error_msg)
            print(f"[DeepSeek] {error_msg}")

        return {'FINISHED'}

    def invoke(self, context, event):
        print("[DeepSeek] Starting autocomplete...")
        return self.execute(context)

def menu_draw(self, context):
    self.layout.operator(DEEPSEEK_OT_AutoComplete.bl_idname)
    self.layout.operator(DEEPSEEK_OT_FixErrors.bl_idname)

addon_keymaps = []

def register():
    bpy.utils.register_class(DeepSeekPreferences)
    bpy.utils.register_class(DEEPSEEK_OT_AutoComplete)
    bpy.utils.register_class(DEEPSEEK_OT_FixErrors)
    TEXT_MT_editor_menus.append(menu_draw)
    
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='Text', space_type='TEXT_EDITOR')
        kmi = km.keymap_items.new(
            DEEPSEEK_OT_AutoComplete.bl_idname,
            'SPACE',
            'PRESS',
            ctrl=True,
            shift=False
        )
        addon_keymaps.append((km, kmi))

    # En la función register()
    km = kc.keymaps.new(name='Text', space_type='TEXT_EDITOR')
    kmi = km.keymap_items.new(
        DEEPSEEK_OT_FixErrors.bl_idname,
        'F8',
        'PRESS',
        ctrl=False,
        shift=False
    )

def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    
    bpy.utils.unregister_class(DeepSeekPreferences)
    bpy.utils.unregister_class(DEEPSEEK_OT_AutoComplete)
    TEXT_MT_editor_menus.remove(menu_draw)
    bpy.utils.unregister_class(DEEPSEEK_OT_FixErrors)

bl_info = {
    "name": "AI DeepSeek Autocomplete for Blender",
    "author": "Jer NC",
    "version": (1, 2),
    "blender": (4, 2, 0),
    "location": "Text Editor > Edit",
    "description": "AI-powered code autocomplete with advanced configuration",
    "category": "Development",
}

if __name__ == "__main__":
    register()