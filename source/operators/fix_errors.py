import bpy
import sys
import io
import re
import traceback
import requests
import threading
from queue import Queue
from bpy.types import Operator

class DEEPSEEK_OT_FixErrors(Operator):
    bl_idname = "text.deepseek_fix_errors"
    bl_label = "DeepSeek Fix Errors"
    bl_description = "Fix Python errors using AI with real-time updates"
    
    _timer = None
    data_queue = Queue()
    is_running = False
    original_text = ""
    error_data = {}
    
    def execute_code(self, context):
        text_block = context.space_data.text
        code = text_block.as_string()
        
        old_stdout, old_stderr = sys.stdout, sys.stderr
        output_buffer = io.StringIO()
        sys.stdout = sys.stderr = output_buffer
        
        try:
            namespace = {'__name__': '__main__', 'bpy': bpy}
            exec(code, namespace)
            error_occurred = False
        except Exception as e:
            error_occurred = True
            traceback.print_exc(file=output_buffer)
            self.error_data = {
                "message": str(e),
                "traceback": output_buffer.getvalue(),
                "code": code
            }
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
            output_buffer.close()
        
        return error_occurred

    def send_to_deepseek(self, context):
        """Thread for sending code to DeepSeek API"""
        try:
            addon_path = '.'.join(__name__.split('.')[:-2])
            prefs = context.preferences.addons[addon_path].preferences
            
            prompt = prefs.error_prompt.format(
                code=self.error_data["code"],
                error=self.error_data["message"],
                console_output=self.error_data["traceback"]
            )
            
            response = requests.post(
                prefs.api_url,
                headers={"Authorization": f"Bearer {prefs.api_key}"},
                json={
                    "model": prefs.model_name_fix_errors,
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
                self.data_queue.put(('SUCCESS', corrected_code))
            else:
                self.data_queue.put(('ERROR', f"API Error: {response.status_code}"))
                
        except Exception as e:
            self.data_queue.put(('ERROR', str(e)))
        finally:
            self.is_running = False

    def modal(self, context, event):
        """Update UI and handle responses"""
        if event.type == 'TIMER':
            while not self.data_queue.empty():
                status, data = self.data_queue.get()
                
                if status == 'SUCCESS':
                    text_block = context.space_data.text
                    text_block.clear()
                    text_block.write(data)
                    self.report({'INFO'}, "Code fixed successfully!")
                    self.cleanup(context)
                    return {'FINISHED'}
                
                elif status == 'ERROR':
                    self.report({'ERROR'}, data)
                    self.cleanup(context)
                    return {'CANCELLED'}
        
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        text_block = context.space_data.text
        self.original_text = text_block.as_string()
        
        if not self.execute_code(context):
            self.report({'INFO'}, "No errors detected")
            return {'FINISHED'}
        
        self.is_running = True
        threading.Thread(target=self.send_to_deepseek, args=(context,)).start()
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        
        self.report({'INFO'}, "Analyzing errors with DeepSeek...")
        return {'RUNNING_MODAL'}

    def cleanup(self, context):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
        self._timer = None

    def clean_response(self, response):
        return re.sub(r'```\w*\s*', '', response).strip()