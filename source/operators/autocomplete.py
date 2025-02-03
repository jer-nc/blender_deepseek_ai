import bpy
import requests
import re
from bpy.types import Operator
import threading
from queue import Queue
import json
import os

class DEEPSEEK_OT_AutoComplete(Operator):
    bl_idname = "text.deepseek_autocomplete"
    bl_label = "DeepSeek Autocomplete"
    bl_description = "Generate code suggestions using AI"
    
    _timer = None
    original_text = ""
    response_buffer = ""
    reasoning_buffer = ""
    stream_active = False
    data_queue = Queue()
    insertion_point = 0

    def get_scene_context(self, context):
        """Get basic scene information"""
        scene = context.scene
        scene_info = []
        
        # Blender info
        scene_info.append(f"Blender Version: {bpy.app.version_string}")
        
        # Basic scene info
        scene_info.append(f"\nScene Name: {scene.name}")
        scene_info.append(f"Total Objects: {len(scene.objects)}")

        # Select objects
        selected_objects = [obj for obj in scene.objects if obj.select_get()]
        scene_info.append(f"Selected Objects: {len(selected_objects)}")
        scene_info.append(f"Selected Objects: {[obj.name for obj in selected_objects]}")

        
        # Cameras
        cameras = [obj for obj in scene.objects if obj.type == 'CAMERA']
        scene_info.append(f"\nCameras ({len(cameras)}):")
        for obj in cameras:
            cam = obj.data
            scene_info.append(f"- {obj.name}: {cam.type} "
                            f"(Focal: {cam.lens}mm, "
                            f"Clip: {cam.clip_start}-{cam.clip_end}m)")
        
        # Lights
        lights = [obj for obj in scene.objects if obj.type == 'LIGHT']
        scene_info.append(f"\nLights ({len(lights)}):")
        for obj in lights:
            light = obj.data
            scene_info.append(f"- {obj.name}: {light.type} "
                            f"(Power: {light.energy}W, "
                            f"Color: {tuple(round(c, 2) for c in light.color)})")
        
        # Meshes
        meshes = [obj for obj in scene.objects if obj.type == 'MESH']
        scene_info.append(f"\nMeshes ({len(meshes)}):")
        for obj in meshes:
            scene_info.append(f"- {obj.name}")
        
        
        # Render settings
        scene_info.append("\nRender Settings:")
        scene_info.append(f"- Engine: {scene.render.engine}")
        
        return '\n'.join(scene_info)

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
        response = re.sub(r'\bNone\b', '', response)
        response = re.sub(r'```\w*\s*', '', response, flags=re.MULTILINE)
        response = re.sub(r'\n{3,}', '\n\n', response)
        return response.strip()
 

    def stream_generation(self, context, full_prompt):
        try:
            addon_path = '.'.join(__name__.split('.')[:-2])
            prefs = context.preferences.addons[addon_path].preferences
            
            print(f"Starting API request to: {prefs.api_url}")

            # Verify API key and URL settings before making the request
            if prefs.api_url.startswith("https://api.openai.com"):
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("La variable de entorno OPENAI_API_KEY no está definida")
                auth_header = f"Bearer {api_key}"
            else:
                auth_header = f"Bearer {prefs.api_key}"


            response = requests.post(
                prefs.api_url,
                headers={
                    # "Authorization": f"Bearer {prefs.api_key}",
                    "Authorization": auth_header,
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
                    "stream": True
                },
                timeout=120,
                stream=True
            )

            # Check HTTP response status
            if response.status_code != 200:
                print(f"API error: Code {response.status_code} - {response.text}")
                self.data_queue.put(('error', f"HTTP Error {response.status_code}"))
                return

            print("Streaming connection successfully established")
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data:'):
                        data = decoded_line[5:].strip()
                        if data == '[DONE]':
                            print("Stream successfully completed")
                            self.data_queue.put(('done', None))
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk['choices'][0]['delta']
                            
                            reasoning_content = delta.get('reasoning_content') or ""
                            self.reasoning_buffer += str(reasoning_content).replace("None", "")
                            if reasoning_content.strip():
                                self.data_queue.put(('reasoning', self.reasoning_buffer))
                            
                            response_content = delta.get('content') or ""
                            self.response_buffer += str(response_content).replace("None", "")
                            if response_content.strip():
                                self.data_queue.put(('content', self.response_buffer))
                                
                        except json.JSONDecodeError as e:
                            print(f"Error decoding JSON: {e}\nReceived data: {decoded_line}")
                            self.data_queue.put(('error', "Invalid JSON response"))
                        except KeyError as e:
                            print(f"Unexpected response structure: {e}\nData: {chunk}")
                            self.data_queue.put(('error', "Invalid response format"))

        except requests.exceptions.RequestException as e:
            error_msg = f"Connection error: {str(e)}"
            print(error_msg)
            self.data_queue.put(('error', error_msg))
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.data_queue.put(('error', error_msg))
        finally:
            self.stream_active = False
            print("Stream ended")

    def modal(self, context, event):
        if event.type == 'TIMER':
            while not self.data_queue.empty():
                data_type, data = self.data_queue.get()

                self.reasoning_buffer = str(self.reasoning_buffer or "")
                self.response_buffer = str(self.response_buffer or "")
                
                text_block = context.space_data.text
                full_text = self.original_text + "\n\n"
                
                if self.reasoning_buffer:
                    reasoning_lines = self.reasoning_buffer.split('\n')
                    commented_reasoning = '\n'.join([f"# {line}" if not line.startswith('#') else line 
                                                    for line in reasoning_lines if line.strip()])
                    full_text += "# [Reasoning Process]:\n" + commented_reasoning + "\n\n"
                
                if self.response_buffer:
                    full_text += "# Code:\n" + self.response_buffer
                
                cleaned_text = self.clean_response(full_text)
                text_block.from_string(cleaned_text)
                
                text_block.current_line_index = len(text_block.lines) - 1
                text_block.current_character = len(text_block.current_line.body)
                context.area.tag_redraw()
                
                if data_type == 'done':
                    self.cleanup(context)
                    return {'FINISHED'}
                elif data_type == 'error':
                    print(f"Error during generation: {data}")
                    self.report({'ERROR'}, data)
                    self.cleanup(context)
                    return {'CANCELLED'}
        
        return {'RUNNING_MODAL'}

    def cleanup(self, context):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
        
        text_block = context.space_data.text
        
        # Only add reasoning if it exists and is not empty
        final_parts = [self.original_text]
        
        reasoning_lines = self.reasoning_buffer.split('\n')
        commented_reasoning = '\n'.join([f"# {line}" if not line.startswith('#') else line 
                                        for line in reasoning_lines if line.strip()])
        
        if commented_reasoning:
            final_parts.append("# [Reasoning Process]:\n" + commented_reasoning)
        
        if self.response_buffer.strip():
            final_parts.append("# Code:\n" + self.response_buffer)
        
        final_text = "\n\n".join(final_parts)
        
        text_block.from_string(self.clean_response(final_text))
        self._timer = None
        self.report({'INFO'}, "Code generation completed!")
    
    def invoke(self, context, event):
        print("[DeepSeek] Starting streaming autocomplete...")
        self.report({'INFO'}, "Starting real-time code generation...")
        
        text_block = context.space_data.text
        self.original_text = text_block.as_string()
        self.insertion_point = len(self.original_text)
        self.response_buffer = ""
        self.reasoning_buffer = ""
        self.stream_active = True
        
        addon_path = '.'.join(__name__.split('.')[:-2])
        prefs = context.preferences.addons[addon_path].preferences
        
        code_context = self.get_code_context(context)
        scene_context = self.get_scene_context(context)
        full_prompt = prefs.custom_prompt.format(
            code_context=code_context,
            scene_context=scene_context
        )
        
        threading.Thread(
            target=self.stream_generation,
            args=(context, full_prompt)
        ).start()
        
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}

