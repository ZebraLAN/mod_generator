# cython: language_level=3
# distutils: language=c++
"""cimgui C 接口声明"""

from libc.stdint cimport uint32_t, uint16_t, int32_t
from libcpp cimport bool as cppbool

cdef extern from "cimgui.h":
    # ==========================================================================
    # 基础类型
    # ==========================================================================
    
    ctypedef unsigned int ImGuiID
    ctypedef int ImGuiCol
    ctypedef int ImGuiStyleVar
    ctypedef int ImGuiWindowFlags
    ctypedef int ImGuiChildFlags
    ctypedef int ImGuiInputTextFlags
    ctypedef int ImGuiTreeNodeFlags
    ctypedef int ImGuiSelectableFlags
    ctypedef int ImGuiComboFlags
    ctypedef int ImGuiTabBarFlags
    ctypedef int ImGuiTabItemFlags
    ctypedef int ImGuiTableFlags
    ctypedef int ImGuiTableColumnFlags
    ctypedef int ImGuiTableRowFlags
    ctypedef int ImGuiHoveredFlags
    ctypedef int ImGuiFocusedFlags
    ctypedef int ImDrawFlags
    ctypedef unsigned short ImWchar
    ctypedef unsigned int ImU32
    ctypedef void* ImTextureID

    # ==========================================================================
    # 结构体
    # ==========================================================================
    
    ctypedef struct ImVec2:
        float x
        float y

    ctypedef struct ImVec4:
        float x
        float y
        float z
        float w

    ctypedef struct ImGuiIO:
        ImVec2 DisplaySize
        float DeltaTime
        float IniSavingRate
        const char* IniFilename
        const char* LogFilename
        float FontGlobalScale
        cppbool FontAllowUserScaling
        ImFont* FontDefault
        ImVec2 DisplayFramebufferScale
        # ... 更多字段按需添加
        ImFontAtlas* Fonts

    ctypedef struct ImGuiStyle:
        float Alpha
        float DisabledAlpha
        ImVec2 WindowPadding
        float WindowRounding
        float WindowBorderSize
        ImVec2 WindowMinSize
        ImVec2 WindowTitleAlign
        float ChildRounding
        float ChildBorderSize
        float PopupRounding
        float PopupBorderSize
        ImVec2 FramePadding
        float FrameRounding
        float FrameBorderSize
        ImVec2 ItemSpacing
        ImVec2 ItemInnerSpacing
        ImVec2 CellPadding
        ImVec2 TouchExtraPadding
        float IndentSpacing
        float ColumnsMinSpacing
        float ScrollbarSize
        float ScrollbarRounding
        float GrabMinSize
        float GrabRounding
        float TabRounding
        float TabBorderSize
        # Colors array
        ImVec4* Colors

    ctypedef struct ImFont:
        float FontSize
        float Scale
        ImVec2 DisplayOffset
        # ... 按需添加

    ctypedef struct ImFontConfig:
        void* FontData
        int FontDataSize
        cppbool FontDataOwnedByAtlas
        int FontNo
        float SizePixels
        int OversampleH
        int OversampleV
        cppbool PixelSnapH
        ImVec2 GlyphExtraSpacing
        ImVec2 GlyphOffset
        const ImWchar* GlyphRanges
        float GlyphMinAdvanceX
        float GlyphMaxAdvanceX
        cppbool MergeMode
        unsigned int FontBuilderFlags
        float RasterizerMultiply
        float RasterizerDensity
        ImWchar EllipsisChar
        char Name[40]
        ImFont* DstFont

    ctypedef struct ImFontAtlas:
        # Flags and settings
        unsigned int Flags
        ImTextureID TexID
        int TexDesiredWidth
        int TexGlyphPadding
        cppbool Locked
        void* UserData
        # Build state
        cppbool TexReady
        cppbool TexPixelsUseColors
        unsigned char* TexPixelsAlpha8
        unsigned int* TexPixelsRGBA32
        int TexWidth
        int TexHeight

    ctypedef struct ImDrawList:
        pass  # 不透明类型

    ctypedef struct ImDrawData:
        cppbool Valid
        int CmdListsCount
        int TotalIdxCount
        int TotalVtxCount
        ImVec2 DisplayPos
        ImVec2 DisplaySize
        ImVec2 FramebufferScale

    # ==========================================================================
    # 核心函数
    # ==========================================================================
    
    # Context
    void igCreateContext(ImFontAtlas* shared_font_atlas)
    void igDestroyContext()
    ImGuiIO* igGetIO()
    ImGuiStyle* igGetStyle()
    
    # Frame
    void igNewFrame()
    void igEndFrame()
    void igRender()
    ImDrawData* igGetDrawData()

    # Window
    cppbool igBegin(const char* name, cppbool* p_open, ImGuiWindowFlags flags)
    void igEnd()
    cppbool igBeginChild_Str(const char* str_id, ImVec2 size, ImGuiChildFlags child_flags, ImGuiWindowFlags window_flags)
    cppbool igBeginChild_ID(ImGuiID id, ImVec2 size, ImGuiChildFlags child_flags, ImGuiWindowFlags window_flags)
    void igEndChild()

    # Widgets: Text
    void igText(const char* fmt, ...)
    void igTextColored(ImVec4 col, const char* fmt, ...)
    void igTextDisabled(const char* fmt, ...)
    void igTextWrapped(const char* fmt, ...)
    void igLabelText(const char* label, const char* fmt, ...)
    void igBulletText(const char* fmt, ...)

    # Widgets: Main
    cppbool igButton(const char* label, ImVec2 size)
    cppbool igSmallButton(const char* label)
    cppbool igInvisibleButton(const char* str_id, ImVec2 size, int flags)
    cppbool igArrowButton(const char* str_id, int dir)
    cppbool igCheckbox(const char* label, cppbool* v)
    cppbool igRadioButton_Bool(const char* label, cppbool active)
    cppbool igRadioButton_IntPtr(const char* label, int* v, int v_button)
    void igProgressBar(float fraction, ImVec2 size_arg, const char* overlay)
    void igBullet()
    void igImage(ImTextureID user_texture_id, ImVec2 image_size, ImVec2 uv0, ImVec2 uv1, ImVec4 tint_col, ImVec4 border_col)
    cppbool igImageButton(const char* str_id, ImTextureID user_texture_id, ImVec2 image_size, ImVec2 uv0, ImVec2 uv1, ImVec4 bg_col, ImVec4 tint_col)

    # Widgets: Input
    cppbool igInputText(const char* label, char* buf, size_t buf_size, ImGuiInputTextFlags flags, void* callback, void* user_data)
    cppbool igInputTextMultiline(const char* label, char* buf, size_t buf_size, ImVec2 size, ImGuiInputTextFlags flags, void* callback, void* user_data)
    cppbool igInputInt(const char* label, int* v, int step, int step_fast, ImGuiInputTextFlags flags)
    cppbool igInputFloat(const char* label, float* v, float step, float step_fast, const char* format, ImGuiInputTextFlags flags)
    cppbool igInputInt2(const char* label, int* v, ImGuiInputTextFlags flags)
    cppbool igInputFloat2(const char* label, float* v, const char* format, ImGuiInputTextFlags flags)

    # Widgets: Combo/Listbox
    cppbool igBeginCombo(const char* label, const char* preview_value, ImGuiComboFlags flags)
    void igEndCombo()
    cppbool igSelectable_Bool(const char* label, cppbool selected, ImGuiSelectableFlags flags, ImVec2 size)
    cppbool igSelectable_BoolPtr(const char* label, cppbool* p_selected, ImGuiSelectableFlags flags, ImVec2 size)

    # Widgets: Sliders
    cppbool igSliderFloat(const char* label, float* v, float v_min, float v_max, const char* format, int flags)
    cppbool igSliderInt(const char* label, int* v, int v_min, int v_max, const char* format, int flags)

    # Widgets: Drag
    cppbool igDragFloat(const char* label, float* v, float v_speed, float v_min, float v_max, const char* format, int flags)
    cppbool igDragInt(const char* label, int* v, float v_speed, int v_min, int v_max, const char* format, int flags)

    # Widgets: Color
    cppbool igColorEdit3(const char* label, float* col, int flags)
    cppbool igColorEdit4(const char* label, float* col, int flags)
    cppbool igColorButton(const char* desc_id, ImVec4 col, int flags, ImVec2 size)

    # Widgets: Trees
    cppbool igTreeNode_Str(const char* label)
    cppbool igTreeNode_StrStr(const char* str_id, const char* fmt, ...)
    cppbool igTreeNodeEx_Str(const char* label, ImGuiTreeNodeFlags flags)
    void igTreePop()
    cppbool igCollapsingHeader_TreeNodeFlags(const char* label, ImGuiTreeNodeFlags flags)
    cppbool igCollapsingHeader_BoolPtr(const char* label, cppbool* p_visible, ImGuiTreeNodeFlags flags)
    void igSetNextItemOpen(cppbool is_open, int cond)

    # Widgets: Tabs
    cppbool igBeginTabBar(const char* str_id, ImGuiTabBarFlags flags)
    void igEndTabBar()
    cppbool igBeginTabItem(const char* label, cppbool* p_open, ImGuiTabItemFlags flags)
    void igEndTabItem()

    # Widgets: Tables
    cppbool igBeginTable(const char* str_id, int column, ImGuiTableFlags flags, ImVec2 outer_size, float inner_width)
    void igEndTable()
    void igTableNextRow(ImGuiTableRowFlags row_flags, float min_row_height)
    cppbool igTableNextColumn()
    cppbool igTableSetColumnIndex(int column_n)
    void igTableSetupColumn(const char* label, ImGuiTableColumnFlags flags, float init_width_or_weight, ImGuiID user_id)
    void igTableHeadersRow()

    # Widgets: Menus
    cppbool igBeginMenuBar()
    void igEndMenuBar()
    cppbool igBeginMainMenuBar()
    void igEndMainMenuBar()
    cppbool igBeginMenu(const char* label, cppbool enabled)
    void igEndMenu()
    cppbool igMenuItem_Bool(const char* label, const char* shortcut, cppbool selected, cppbool enabled)
    cppbool igMenuItem_BoolPtr(const char* label, const char* shortcut, cppbool* p_selected, cppbool enabled)

    # Popups, Modals
    cppbool igBeginPopup(const char* str_id, ImGuiWindowFlags flags)
    cppbool igBeginPopupModal(const char* name, cppbool* p_open, ImGuiWindowFlags flags)
    void igEndPopup()
    void igOpenPopup_Str(const char* str_id, int popup_flags)
    void igCloseCurrentPopup()
    cppbool igBeginPopupContextItem(const char* str_id, int popup_flags)
    cppbool igBeginPopupContextWindow(const char* str_id, int popup_flags)
    cppbool igIsPopupOpen_Str(const char* str_id, int flags)

    # Layout
    void igSeparator()
    void igSameLine(float offset_from_start_x, float spacing)
    void igNewLine()
    void igSpacing()
    void igDummy(ImVec2 size)
    void igIndent(float indent_w)
    void igUnindent(float indent_w)
    void igBeginGroup()
    void igEndGroup()
    void igSetCursorPos(ImVec2 local_pos)
    void igSetCursorPosX(float local_x)
    void igSetCursorPosY(float local_y)
    void igGetCursorPos(ImVec2* pOut)
    float igGetCursorPosX()
    float igGetCursorPosY()
    void igGetCursorStartPos(ImVec2* pOut)
    void igGetCursorScreenPos(ImVec2* pOut)
    void igSetCursorScreenPos(ImVec2 pos)
    void igAlignTextToFramePadding()
    float igGetTextLineHeight()
    float igGetTextLineHeightWithSpacing()
    float igGetFrameHeight()
    float igGetFrameHeightWithSpacing()

    # Sizing
    void igPushItemWidth(float item_width)
    void igPopItemWidth()
    void igSetNextItemWidth(float item_width)
    float igCalcItemWidth()
    void igCalcTextSize(ImVec2* pOut, const char* text, const char* text_end, cppbool hide_text_after_double_hash, float wrap_width)
    void igGetContentRegionAvail(ImVec2* pOut)
    void igGetContentRegionMax(ImVec2* pOut)
    void igGetWindowContentRegionMin(ImVec2* pOut)
    void igGetWindowContentRegionMax(ImVec2* pOut)

    # Window utilities
    void igSetNextWindowPos(ImVec2 pos, int cond, ImVec2 pivot)
    void igSetNextWindowSize(ImVec2 size, int cond)
    void igSetNextWindowContentSize(ImVec2 size)
    void igSetNextWindowCollapsed(cppbool collapsed, int cond)
    void igSetNextWindowFocus()
    void igSetNextWindowBgAlpha(float alpha)
    void igGetWindowPos(ImVec2* pOut)
    void igGetWindowSize(ImVec2* pOut)
    float igGetWindowWidth()
    float igGetWindowHeight()
    cppbool igIsWindowAppearing()
    cppbool igIsWindowCollapsed()
    cppbool igIsWindowFocused(ImGuiFocusedFlags flags)
    cppbool igIsWindowHovered(ImGuiHoveredFlags flags)
    ImDrawList* igGetWindowDrawList()
    ImDrawList* igGetForegroundDrawList_Nil()
    ImDrawList* igGetBackgroundDrawList_Nil()

    # Item utilities
    cppbool igIsItemHovered(ImGuiHoveredFlags flags)
    cppbool igIsItemActive()
    cppbool igIsItemFocused()
    cppbool igIsItemClicked(int mouse_button)
    cppbool igIsItemVisible()
    cppbool igIsItemEdited()
    cppbool igIsItemActivated()
    cppbool igIsItemDeactivated()
    cppbool igIsItemDeactivatedAfterEdit()
    cppbool igIsItemToggledOpen()
    cppbool igIsAnyItemHovered()
    cppbool igIsAnyItemActive()
    cppbool igIsAnyItemFocused()
    void igGetItemRectMin(ImVec2* pOut)
    void igGetItemRectMax(ImVec2* pOut)
    void igGetItemRectSize(ImVec2* pOut)
    void igSetItemAllowOverlap()

    # Tooltips
    void igSetTooltip(const char* fmt, ...)
    void igBeginTooltip()
    void igEndTooltip()

    # Style
    void igPushStyleColor_U32(ImGuiCol idx, ImU32 col)
    void igPushStyleColor_Vec4(ImGuiCol idx, ImVec4 col)
    void igPopStyleColor(int count)
    void igPushStyleVar_Float(ImGuiStyleVar idx, float val)
    void igPushStyleVar_Vec2(ImGuiStyleVar idx, ImVec2 val)
    void igPopStyleVar(int count)
    ImU32 igGetColorU32_Col(ImGuiCol idx, float alpha_mul)
    ImU32 igGetColorU32_Vec4(ImVec4 col)
    ImU32 igGetColorU32_U32(ImU32 col)

    # Font
    void igPushFont(ImFont* font)
    void igPopFont()
    ImFont* igGetFont()
    float igGetFontSize()
    void igGetFontTexUvWhitePixel(ImVec2* pOut)

    # ID
    void igPushID_Str(const char* str_id)
    void igPushID_StrStr(const char* str_id_begin, const char* str_id_end)
    void igPushID_Int(int int_id)
    void igPopID()
    ImGuiID igGetID_Str(const char* str_id)
    ImGuiID igGetID_StrStr(const char* str_id_begin, const char* str_id_end)

    # Scrolling
    float igGetScrollX()
    float igGetScrollY()
    void igSetScrollX_Float(float scroll_x)
    void igSetScrollY_Float(float scroll_y)
    float igGetScrollMaxX()
    float igGetScrollMaxY()
    void igSetScrollHereX(float center_x_ratio)
    void igSetScrollHereY(float center_y_ratio)
    void igSetScrollFromPosX_Float(float local_x, float center_x_ratio)
    void igSetScrollFromPosY_Float(float local_y, float center_y_ratio)

    # Keyboard/Mouse
    cppbool igIsKeyDown_Nil(int key)
    cppbool igIsKeyPressed_Bool(int key, cppbool repeat)
    cppbool igIsKeyReleased_Nil(int key)
    cppbool igIsMouseDown_Nil(int button)
    cppbool igIsMouseClicked_Bool(int button, cppbool repeat)
    cppbool igIsMouseReleased_Nil(int button)
    cppbool igIsMouseDoubleClicked(int button)
    cppbool igIsMouseHoveringRect(ImVec2 r_min, ImVec2 r_max, cppbool clip)
    void igGetMousePos(ImVec2* pOut)
    void igGetMousePosOnOpeningCurrentPopup(ImVec2* pOut)
    cppbool igIsMouseDragging(int button, float lock_threshold)
    void igGetMouseDragDelta(ImVec2* pOut, int button, float lock_threshold)
    void igResetMouseDragDelta(int button)

    # Clipboard
    const char* igGetClipboardText()
    void igSetClipboardText(const char* text)

    # ==========================================================================
    # ImFontAtlas 函数 - 关键字体 API！
    # ==========================================================================
    
    ImFontAtlas* ImFontAtlas_ImFontAtlas()
    void ImFontAtlas_destroy(ImFontAtlas* self)
    ImFont* ImFontAtlas_AddFont(ImFontAtlas* self, const ImFontConfig* font_cfg)
    ImFont* ImFontAtlas_AddFontDefault(ImFontAtlas* self, const ImFontConfig* font_cfg)
    ImFont* ImFontAtlas_AddFontFromFileTTF(ImFontAtlas* self, const char* filename, float size_pixels, const ImFontConfig* font_cfg, const ImWchar* glyph_ranges)
    ImFont* ImFontAtlas_AddFontFromMemoryTTF(ImFontAtlas* self, void* font_data, int font_data_size, float size_pixels, const ImFontConfig* font_cfg, const ImWchar* glyph_ranges)
    ImFont* ImFontAtlas_AddFontFromMemoryCompressedTTF(ImFontAtlas* self, const void* compressed_font_data, int compressed_font_data_size, float size_pixels, const ImFontConfig* font_cfg, const ImWchar* glyph_ranges)
    ImFont* ImFontAtlas_AddFontFromMemoryCompressedBase85TTF(ImFontAtlas* self, const char* compressed_font_data_base85, float size_pixels, const ImFontConfig* font_cfg, const ImWchar* glyph_ranges)
    void ImFontAtlas_ClearInputData(ImFontAtlas* self)
    void ImFontAtlas_ClearTexData(ImFontAtlas* self)
    void ImFontAtlas_ClearFonts(ImFontAtlas* self)
    void ImFontAtlas_Clear(ImFontAtlas* self)
    cppbool ImFontAtlas_Build(ImFontAtlas* self)
    void ImFontAtlas_GetTexDataAsAlpha8(ImFontAtlas* self, unsigned char** out_pixels, int* out_width, int* out_height, int* out_bytes_per_pixel)
    void ImFontAtlas_GetTexDataAsRGBA32(ImFontAtlas* self, unsigned char** out_pixels, int* out_width, int* out_height, int* out_bytes_per_pixel)
    cppbool ImFontAtlas_IsBuilt(ImFontAtlas* self)
    void ImFontAtlas_SetTexID(ImFontAtlas* self, ImTextureID id)
    
    # Glyph ranges
    const ImWchar* ImFontAtlas_GetGlyphRangesDefault(ImFontAtlas* self)
    const ImWchar* ImFontAtlas_GetGlyphRangesGreek(ImFontAtlas* self)
    const ImWchar* ImFontAtlas_GetGlyphRangesKorean(ImFontAtlas* self)
    const ImWchar* ImFontAtlas_GetGlyphRangesJapanese(ImFontAtlas* self)
    const ImWchar* ImFontAtlas_GetGlyphRangesChineseFull(ImFontAtlas* self)
    const ImWchar* ImFontAtlas_GetGlyphRangesChineseSimplifiedCommon(ImFontAtlas* self)
    const ImWchar* ImFontAtlas_GetGlyphRangesCyrillic(ImFontAtlas* self)
    const ImWchar* ImFontAtlas_GetGlyphRangesThai(ImFontAtlas* self)
    const ImWchar* ImFontAtlas_GetGlyphRangesVietnamese(ImFontAtlas* self)

    # ==========================================================================
    # ImDrawList 函数
    # ==========================================================================
    
    void ImDrawList_AddLine(ImDrawList* self, ImVec2 p1, ImVec2 p2, ImU32 col, float thickness)
    void ImDrawList_AddRect(ImDrawList* self, ImVec2 p_min, ImVec2 p_max, ImU32 col, float rounding, ImDrawFlags flags, float thickness)
    void ImDrawList_AddRectFilled(ImDrawList* self, ImVec2 p_min, ImVec2 p_max, ImU32 col, float rounding, ImDrawFlags flags)
    void ImDrawList_AddCircle(ImDrawList* self, ImVec2 center, float radius, ImU32 col, int num_segments, float thickness)
    void ImDrawList_AddCircleFilled(ImDrawList* self, ImVec2 center, float radius, ImU32 col, int num_segments)
    void ImDrawList_AddTriangle(ImDrawList* self, ImVec2 p1, ImVec2 p2, ImVec2 p3, ImU32 col, float thickness)
    void ImDrawList_AddTriangleFilled(ImDrawList* self, ImVec2 p1, ImVec2 p2, ImVec2 p3, ImU32 col)
    void ImDrawList_AddText_Vec2(ImDrawList* self, ImVec2 pos, ImU32 col, const char* text_begin, const char* text_end)
    void ImDrawList_AddText_FontPtr(ImDrawList* self, const ImFont* font, float font_size, ImVec2 pos, ImU32 col, const char* text_begin, const char* text_end, float wrap_width, const ImVec4* cpu_fine_clip_rect)
    void ImDrawList_AddImage(ImDrawList* self, ImTextureID user_texture_id, ImVec2 p_min, ImVec2 p_max, ImVec2 uv_min, ImVec2 uv_max, ImU32 col)
    void ImDrawList_AddImageRounded(ImDrawList* self, ImTextureID user_texture_id, ImVec2 p_min, ImVec2 p_max, ImVec2 uv_min, ImVec2 uv_max, ImU32 col, float rounding, ImDrawFlags flags)

    # ==========================================================================
    # ImFontConfig 工具
    # ==========================================================================
    
    ImFontConfig* ImFontConfig_ImFontConfig()
    void ImFontConfig_destroy(ImFontConfig* self)


# ==========================================================================
# 后端 - GLFW + OpenGL3
# ==========================================================================

cdef extern from "imgui_impl_glfw.h":
    cppbool ImGui_ImplGlfw_InitForOpenGL(void* window, cppbool install_callbacks)
    cppbool ImGui_ImplGlfw_InitForVulkan(void* window, cppbool install_callbacks)
    cppbool ImGui_ImplGlfw_InitForOther(void* window, cppbool install_callbacks)
    void ImGui_ImplGlfw_Shutdown()
    void ImGui_ImplGlfw_NewFrame()

cdef extern from "imgui_impl_opengl3.h":
    cppbool ImGui_ImplOpenGL3_Init(const char* glsl_version)
    void ImGui_ImplOpenGL3_Shutdown()
    void ImGui_ImplOpenGL3_NewFrame()
    void ImGui_ImplOpenGL3_RenderDrawData(ImDrawData* draw_data)
    cppbool ImGui_ImplOpenGL3_CreateFontsTexture()
    void ImGui_ImplOpenGL3_DestroyFontsTexture()
    cppbool ImGui_ImplOpenGL3_CreateDeviceObjects()
    void ImGui_ImplOpenGL3_DestroyDeviceObjects()


# ==========================================================================
# 常量 (枚举)
# ==========================================================================

cdef extern from "cimgui.h":
    # ImGuiCol_
    cdef int ImGuiCol_Text
    cdef int ImGuiCol_TextDisabled
    cdef int ImGuiCol_WindowBg
    cdef int ImGuiCol_ChildBg
    cdef int ImGuiCol_PopupBg
    cdef int ImGuiCol_Border
    cdef int ImGuiCol_BorderShadow
    cdef int ImGuiCol_FrameBg
    cdef int ImGuiCol_FrameBgHovered
    cdef int ImGuiCol_FrameBgActive
    cdef int ImGuiCol_TitleBg
    cdef int ImGuiCol_TitleBgActive
    cdef int ImGuiCol_TitleBgCollapsed
    cdef int ImGuiCol_MenuBarBg
    cdef int ImGuiCol_ScrollbarBg
    cdef int ImGuiCol_ScrollbarGrab
    cdef int ImGuiCol_ScrollbarGrabHovered
    cdef int ImGuiCol_ScrollbarGrabActive
    cdef int ImGuiCol_CheckMark
    cdef int ImGuiCol_SliderGrab
    cdef int ImGuiCol_SliderGrabActive
    cdef int ImGuiCol_Button
    cdef int ImGuiCol_ButtonHovered
    cdef int ImGuiCol_ButtonActive
    cdef int ImGuiCol_Header
    cdef int ImGuiCol_HeaderHovered
    cdef int ImGuiCol_HeaderActive
    cdef int ImGuiCol_Separator
    cdef int ImGuiCol_SeparatorHovered
    cdef int ImGuiCol_SeparatorActive
    cdef int ImGuiCol_ResizeGrip
    cdef int ImGuiCol_ResizeGripHovered
    cdef int ImGuiCol_ResizeGripActive
    cdef int ImGuiCol_Tab
    cdef int ImGuiCol_TabHovered
    cdef int ImGuiCol_TabActive
    cdef int ImGuiCol_TabUnfocused
    cdef int ImGuiCol_TabUnfocusedActive
    cdef int ImGuiCol_PlotLines
    cdef int ImGuiCol_PlotLinesHovered
    cdef int ImGuiCol_PlotHistogram
    cdef int ImGuiCol_PlotHistogramHovered
    cdef int ImGuiCol_TableHeaderBg
    cdef int ImGuiCol_TableBorderStrong
    cdef int ImGuiCol_TableBorderLight
    cdef int ImGuiCol_TableRowBg
    cdef int ImGuiCol_TableRowBgAlt
    cdef int ImGuiCol_TextSelectedBg
    cdef int ImGuiCol_DragDropTarget
    cdef int ImGuiCol_NavHighlight
    cdef int ImGuiCol_NavWindowingHighlight
    cdef int ImGuiCol_NavWindowingDimBg
    cdef int ImGuiCol_ModalWindowDimBg
    cdef int ImGuiCol_COUNT

    # ImGuiStyleVar_
    cdef int ImGuiStyleVar_Alpha
    cdef int ImGuiStyleVar_DisabledAlpha
    cdef int ImGuiStyleVar_WindowPadding
    cdef int ImGuiStyleVar_WindowRounding
    cdef int ImGuiStyleVar_WindowBorderSize
    cdef int ImGuiStyleVar_WindowMinSize
    cdef int ImGuiStyleVar_WindowTitleAlign
    cdef int ImGuiStyleVar_ChildRounding
    cdef int ImGuiStyleVar_ChildBorderSize
    cdef int ImGuiStyleVar_PopupRounding
    cdef int ImGuiStyleVar_PopupBorderSize
    cdef int ImGuiStyleVar_FramePadding
    cdef int ImGuiStyleVar_FrameRounding
    cdef int ImGuiStyleVar_FrameBorderSize
    cdef int ImGuiStyleVar_ItemSpacing
    cdef int ImGuiStyleVar_ItemInnerSpacing
    cdef int ImGuiStyleVar_IndentSpacing
    cdef int ImGuiStyleVar_CellPadding
    cdef int ImGuiStyleVar_ScrollbarSize
    cdef int ImGuiStyleVar_ScrollbarRounding
    cdef int ImGuiStyleVar_GrabMinSize
    cdef int ImGuiStyleVar_GrabRounding
    cdef int ImGuiStyleVar_TabRounding
    cdef int ImGuiStyleVar_ButtonTextAlign
    cdef int ImGuiStyleVar_SelectableTextAlign

    # ImGuiWindowFlags_
    cdef int ImGuiWindowFlags_None
    cdef int ImGuiWindowFlags_NoTitleBar
    cdef int ImGuiWindowFlags_NoResize
    cdef int ImGuiWindowFlags_NoMove
    cdef int ImGuiWindowFlags_NoScrollbar
    cdef int ImGuiWindowFlags_NoScrollWithMouse
    cdef int ImGuiWindowFlags_NoCollapse
    cdef int ImGuiWindowFlags_AlwaysAutoResize
    cdef int ImGuiWindowFlags_NoBackground
    cdef int ImGuiWindowFlags_NoSavedSettings
    cdef int ImGuiWindowFlags_NoMouseInputs
    cdef int ImGuiWindowFlags_MenuBar
    cdef int ImGuiWindowFlags_HorizontalScrollbar
    cdef int ImGuiWindowFlags_NoFocusOnAppearing
    cdef int ImGuiWindowFlags_NoBringToFrontOnFocus
    cdef int ImGuiWindowFlags_AlwaysVerticalScrollbar
    cdef int ImGuiWindowFlags_AlwaysHorizontalScrollbar
    cdef int ImGuiWindowFlags_AlwaysUseWindowPadding
    cdef int ImGuiWindowFlags_NoNavInputs
    cdef int ImGuiWindowFlags_NoNavFocus
    cdef int ImGuiWindowFlags_UnsavedDocument
    cdef int ImGuiWindowFlags_NoNav
    cdef int ImGuiWindowFlags_NoDecoration
    cdef int ImGuiWindowFlags_NoInputs

    # ImGuiHoveredFlags_
    cdef int ImGuiHoveredFlags_None
    cdef int ImGuiHoveredFlags_ChildWindows
    cdef int ImGuiHoveredFlags_RootWindow
    cdef int ImGuiHoveredFlags_AnyWindow
    cdef int ImGuiHoveredFlags_AllowWhenBlockedByPopup
    cdef int ImGuiHoveredFlags_AllowWhenBlockedByActiveItem
    cdef int ImGuiHoveredFlags_AllowWhenOverlapped
    cdef int ImGuiHoveredFlags_AllowWhenDisabled
    cdef int ImGuiHoveredFlags_RectOnly
