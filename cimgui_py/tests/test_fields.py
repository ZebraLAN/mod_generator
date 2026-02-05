import sys
sys.path.insert(0, r"c:\Users\davie\Stoneshard Modding\mod_generator\cimgui_py")
import src.cimgui_py.core as imgui

# 创建 context
ctx = imgui.create_context()
print(f'Context: {ctx}')

# 获取 IO
io = imgui.get_io()
print(f'IO: {io}')

# 测试标量字段访问
print(f'io.delta_time = {io.delta_time}')
print(f'io.ini_saving_rate = {io.ini_saving_rate}')
print(f'io.want_capture_mouse = {io.want_capture_mouse}')

# 测试 ImVec2 字段
print(f'io.display_size = {io.display_size}')
io.display_size = (1920, 1080)
print(f'io.display_size after set = {io.display_size}')

# 测试 bool 字段
print(f'io.config_docking_no_split = {io.config_docking_no_split}')
io.config_docking_no_split = True
print(f'io.config_docking_no_split after set = {io.config_docking_no_split}')

# 测试 memoryview 数组字段
print('\n=== Memoryview Array Access ===')
mouse_down = io.mouse_down
print(f'io.mouse_down type: {type(mouse_down)}')
print(f'io.mouse_down[0] = {mouse_down[0]}')
print(f'io.mouse_down[1] = {mouse_down[1]}')

# 测试通过 memoryview 修改
mouse_down[0] = True
print(f'io.mouse_down[0] after set = {io.mouse_down[0]}')

# 测试 Style
style = imgui.get_style()
print(f'\nStyle: {style}')
print(f'style.alpha = {style.alpha}')
print(f'style.window_padding = {style.window_padding}')

# 清理
imgui.destroy_context(ctx)
print('\nSuccess!')
