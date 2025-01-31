import bpy
import requests
import re
from bpy.types import Operator

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
        # This is the path to the addon without the operator name
        addon_path = '.'.join(__name__.split('.')[:-2]) 
        print("Addon path without 'operators.autocomplete':", addon_path)
        prefs = context.preferences.addons[addon_path].preferences
        
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
        print("Context: ", context)
        print("Self: ", self)
        # print("prefs: ", context.preferences.addons[__name__].preferences)
        print("[DeepSeek] Starting autocomplete...")
        return self.execute(context)