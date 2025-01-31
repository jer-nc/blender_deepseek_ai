import bpy
import sys
import io
import re
import traceback
import requests
from bpy.types import Operator

class DEEPSEEK_OT_FixErrors(Operator):
    bl_idname = "text.deepseek_fix_errors"
    bl_label = "DeepSeek Fix Errors"
    bl_description = "Fix Python errors using AI, this will execute the code and send the error to DeepSeek"
    
    def execute(self, context):
        # prefs = context.preferences.addons[__name__].preferences
        addon_path = '.'.join(__name__.split('.')[:-2]) 
        print("Addon path without 'operators.fix_errors':", addon_path)
        prefs = context.preferences.addons[addon_path].preferences
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