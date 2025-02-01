import bpy
from .properties import DeepSeekProperties
from .operators.autocomplete import DEEPSEEK_OT_AutoComplete
from .operators.fix_errors import DEEPSEEK_OT_FixErrors

class DeepSeekPreferences(bpy.types.AddonPreferences, DeepSeekProperties):
    bl_idname = __name__

    def draw(self, context):
        layout = self.layout
        layout.label(text="API Configuration:")
        layout.prop(self, "api_key")
        layout.prop(self, "api_url")
        layout.prop(self, "model_name")
        layout.prop(self, "model_name_fix_errors")
        
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

def menu_draw(self, context):
    self.layout.operator(DEEPSEEK_OT_AutoComplete.bl_idname)
    self.layout.operator(DEEPSEEK_OT_FixErrors.bl_idname)

addon_keymaps = []

def register():
    bpy.utils.register_class(DeepSeekPreferences)
    bpy.utils.register_class(DEEPSEEK_OT_AutoComplete)
    bpy.utils.register_class(DEEPSEEK_OT_FixErrors)
    bpy.types.TEXT_MT_editor_menus.append(menu_draw)

    # CTRL + SPACE to trigger autocomplete
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

    # F8 to trigger error correction
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
    bpy.utils.unregister_class(DEEPSEEK_OT_FixErrors)
    bpy.types.TEXT_MT_editor_menus.remove(menu_draw)
