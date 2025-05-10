import tkinter as tk
from tkinter import filedialog, ttk, colorchooser
from PIL import Image, ImageTk, ImageDraw, ImageFont # For preview
import os
import threading # To prevent GUI freeze during rendering

from core.parser import parse_subtitle_file, SubtitleEntry
from core.renderer import render_subtitle_image, DEFAULT_SETTINGS, RESOLUTIONS, get_font
from core.utils import sanitize_filename

class SubtitleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("高级字幕图层生成器")
        # Increased window width to accommodate larger preview and new button
        self.root.geometry("1300x700")

        self.subtitle_file_path = tk.StringVar()
        self.output_directory = tk.StringVar(value=DEFAULT_SETTINGS["output_directory"])
        self.preview_background_image_pil = None # To store the loaded PIL Image for background
        
        # --- Current settings ---
        # These will be dictionaries holding settings for 'original' and 'translation'
        self._resize_job = None # For debouncing resize events
        self.current_settings = {
            "common": DEFAULT_SETTINGS.copy(),
            "original": { # These will be fully populated by DEFAULT_SETTINGS
                "font_path": DEFAULT_SETTINGS["font_path_original"],
                "font_size": DEFAULT_SETTINGS["font_size_original"],
                "font_color": DEFAULT_SETTINGS["font_color_original"], # RGBA
                "effects": DEFAULT_SETTINGS["effects_original"].copy()
            },
            "translation": {
                "font_path": DEFAULT_SETTINGS["font_path_translation"],
                "font_size": DEFAULT_SETTINGS["font_size_translation"],
                "font_color": DEFAULT_SETTINGS["font_color_translation"], # RGBA
                "effects": DEFAULT_SETTINGS["effects_translation"].copy()
            }
        }
        # Clean up common settings that are now per-text_type or specific to non-custom alignment
        # Keep resolution, output_directory, text_align, position_y_offset, line_spacing in common
        # Custom X/Y coords are also in common as they define overall placement strategy
        keys_to_remove_from_common = [
            "font_path_original", "font_size_original", "font_color_original", "effects_original",
            "font_path_translation", "font_size_translation", "font_color_translation", "effects_translation"
        ]
        for key in keys_to_remove_from_common:
            if key in self.current_settings["common"]:
                del self.current_settings["common"][key]
        
        # Ensure custom_xy related keys from DEFAULT_SETTINGS are in self.current_settings["common"]
        # (they should be already due to .copy(), but good to be explicit if needed for new keys)
        # self.current_settings["common"]["custom_x_original"] = DEFAULT_SETTINGS["custom_x_original"]
        # ... and so on for other custom_x/y keys if they weren't part of the initial copy.

        # --- Main Layout ---
        # Top: File selection and output directory
        top_frame = ttk.Frame(root, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="字幕文件:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(top_frame, textvariable=self.subtitle_file_path, width=50).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Button(top_frame, text="浏览...", command=self.browse_subtitle_file).pack(side=tk.LEFT, padx=5)

        ttk.Label(top_frame, text="输出目录:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(top_frame, textvariable=self.output_directory, width=30).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        ttk.Button(top_frame, text="选择目录...", command=self.browse_output_directory).pack(side=tk.LEFT, padx=5)

        self.add_preview_bg_button = ttk.Button(top_frame, text="添加预览背景", command=self.browse_preview_background)
        self.add_preview_bg_button.pack(side=tk.LEFT, padx=(20,2)) # Add some space before it, increased left padding

        self.generate_button = ttk.Button(top_frame, text="生成PNG图片", command=self.start_generation_thread)
        self.generate_button.pack(side=tk.LEFT, padx=(5,5)) # Adjusted padding

        self.status_label = ttk.Label(top_frame, text="准备就绪", width=20) # Give it a default width
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=False, padx=5) # Don't expand status too much initially
        
        # Main content: Settings (left) and Preview (right)
        main_content_frame = ttk.Frame(root, padding="10")
        main_content_frame.pack(fill=tk.BOTH, expand=True)

        self.settings_notebook = ttk.Notebook(main_content_frame)
        self.settings_notebook.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10, anchor=tk.N)
        
        # Common settings tab (Resolution, Position, etc.)
        common_settings_frame = ttk.Frame(self.settings_notebook, padding="10")
        self.settings_notebook.add(common_settings_frame, text="通用设置")
        self.create_common_settings_ui(common_settings_frame)

        # Original Text (Sub) settings tab
        original_settings_frame = ttk.Frame(self.settings_notebook, padding="10")
        self.settings_notebook.add(original_settings_frame, text="主字幕 (Sub)")
        self.create_text_style_ui(original_settings_frame, "original")

        # Translation Text (SubCh) settings tab
        translation_settings_frame = ttk.Frame(self.settings_notebook, padding="10")
        self.settings_notebook.add(translation_settings_frame, text="翻译字幕 (SubCh)")
        self.create_text_style_ui(translation_settings_frame, "translation")

        self.main_content_frame = main_content_frame # Store reference
        # self.main_content_frame.bind("<Configure>", self.on_main_content_resize) # Removed for fixed preview size

        # Preview Area
        fixed_preview_width = 960  # Increased width for preview (16:9 aspect ratio)
        fixed_preview_height = 540 # Increased height for preview
        self.preview_frame = ttk.LabelFrame(main_content_frame, text="预览", padding="10",
                                            width=fixed_preview_width, height=fixed_preview_height)
        self.preview_frame.pack_propagate(False) # Prevent children from resizing this frame
        # Pack with fixed size, no expand, ensure top alignment
        self.preview_frame.pack(side=tk.RIGHT, fill=tk.NONE, expand=False, padx=10, pady=10, anchor=tk.N)
        
        self.preview_label = ttk.Label(self.preview_frame) # Removed background="gray"
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        # update_preview_on_resize is still useful as preview_label's size is set by preview_frame
        self.preview_label.bind("<Configure>", self.update_preview_on_resize)

        # Bottom frame is no longer needed for generate button and status
        # bottom_frame = ttk.Frame(root, padding="10")
        # bottom_frame.pack(fill=tk.X)
        
        # self.generate_button = ttk.Button(bottom_frame, text="生成PNG图片", command=self.start_generation_thread)
        # self.generate_button.pack(side=tk.LEFT, padx=5)
        
        # self.status_label = ttk.Label(bottom_frame, text="准备就绪")
        # self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Delay initial preview setup slightly to allow window to stabilize
        self.root.after(100, self.update_preview) # Initial preview with fixed size

    def browse_subtitle_file(self):
        path = filedialog.askopenfilename(
            title="选择字幕文件",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        if path:
            self.subtitle_file_path.set(path)
            self.status_label.config(text=f"已选择字幕文件: {os.path.basename(path)}")

    def browse_output_directory(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_directory.set(path)
            self.current_settings["common"]["output_directory"] = path
            self.status_label.config(text=f"输出目录已设置为: {path}")

    def browse_preview_background(self):
        path = filedialog.askopenfilename(
            title="选择预览背景图片",
            filetypes=(("Image files", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All files", "*.*"))
        )
        if path:
            try:
                self.preview_background_image_pil = Image.open(path)
                # Ensure it's RGBA for consistency if we need to alpha_composite later
                # However, for background, RGB is fine if it's opaque.
                # Let's convert to RGBA to handle transparency in the source if any,
                # and to make it simpler for compositing.
                if self.preview_background_image_pil.mode != "RGBA":
                    self.preview_background_image_pil = self.preview_background_image_pil.convert("RGBA")
                
                self.status_label.config(text=f"预览背景已加载: {os.path.basename(path)}")
                self.update_preview() # Update preview with new background
            except Exception as e:
                self.preview_background_image_pil = None # Reset on error
                self.status_label.config(text=f"错误: 加载背景图片失败 - {e}")
                print(f"Error loading preview background: {e}")


    def create_common_settings_ui(self, parent_frame):
        ttk.Label(parent_frame, text="分辨率:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.resolution_var = tk.StringVar(value=self.current_settings["common"]["resolution"])
        resolution_combo = ttk.Combobox(parent_frame, textvariable=self.resolution_var, 
                                        values=list(RESOLUTIONS.keys()), state="readonly", width=15)
        resolution_combo.grid(row=0, column=1, sticky=tk.EW, pady=2)
        resolution_combo.bind("<<ComboboxSelected>>", lambda e: self.update_setting("common", "resolution", self.resolution_var.get(), True))

        # Y轴偏移 (从底部) 控件已移除
        # 行间距 (主字幕与翻译间) 控件已移除
        
        ttk.Label(parent_frame, text="文本对齐:").grid(row=1, column=0, sticky=tk.W, pady=2) # Row changed from 2 to 1
        self.text_align_var = tk.StringVar(value=self.current_settings["common"]["text_align"])
        align_values = ["left", "center", "right"]
        self.align_combo = ttk.Combobox(parent_frame, textvariable=self.text_align_var,
                                   values=align_values, state="readonly", width=15)
        self.align_combo.grid(row=1, column=1, sticky=tk.EW, pady=2) # Row changed from 2 to 1
        self.align_combo.bind("<<ComboboxSelected>>", self.on_align_mode_change)

        # Custom XY Coordinate Inputs
        custom_xy_row_start = 2 # Row changed from 3 to 2
        ttk.Label(parent_frame, text="主字幕 X:").grid(row=custom_xy_row_start, column=0, sticky=tk.W, pady=1)
        self.custom_x_orig_var = tk.IntVar(value=self.current_settings["common"].get("custom_x_original",0))
        self.custom_x_orig_spin = ttk.Spinbox(parent_frame, from_=0, to=4000, textvariable=self.custom_x_orig_var, width=7,
                                        command=lambda: self.update_setting("common", "custom_x_original", self.custom_x_orig_var.get(), True))
        self.custom_x_orig_var.trace_add("write", lambda *args: self.update_setting("common", "custom_x_original", self.custom_x_orig_var.get(), True))
        self.custom_x_orig_spin.grid(row=custom_xy_row_start, column=1, sticky=tk.W, pady=1)

        ttk.Label(parent_frame, text="主字幕 Y:").grid(row=custom_xy_row_start+1, column=0, sticky=tk.W, pady=1)
        self.custom_y_orig_var = tk.IntVar(value=self.current_settings["common"].get("custom_y_original",0))
        self.custom_y_orig_spin = ttk.Spinbox(parent_frame, from_=0, to=4000, textvariable=self.custom_y_orig_var, width=7,
                                        command=lambda: self.update_setting("common", "custom_y_original", self.custom_y_orig_var.get(), True))
        self.custom_y_orig_var.trace_add("write", lambda *args: self.update_setting("common", "custom_y_original", self.custom_y_orig_var.get(), True))
        self.custom_y_orig_spin.grid(row=custom_xy_row_start+1, column=1, sticky=tk.W, pady=1)

        ttk.Label(parent_frame, text="翻译字幕 X:").grid(row=custom_xy_row_start+2, column=0, sticky=tk.W, pady=1)
        self.custom_x_trans_var = tk.IntVar(value=self.current_settings["common"].get("custom_x_translation",0))
        self.custom_x_trans_spin = ttk.Spinbox(parent_frame, from_=0, to=4000, textvariable=self.custom_x_trans_var, width=7,
                                        command=lambda: self.update_setting("common", "custom_x_translation", self.custom_x_trans_var.get(), True))
        self.custom_x_trans_var.trace_add("write", lambda *args: self.update_setting("common", "custom_x_translation", self.custom_x_trans_var.get(), True))
        self.custom_x_trans_spin.grid(row=custom_xy_row_start+2, column=1, sticky=tk.W, pady=1)

        ttk.Label(parent_frame, text="翻译字幕 Y:").grid(row=custom_xy_row_start+3, column=0, sticky=tk.W, pady=1)
        self.custom_y_trans_var = tk.IntVar(value=self.current_settings["common"].get("custom_y_translation",0))
        self.custom_y_trans_spin = ttk.Spinbox(parent_frame, from_=0, to=4000, textvariable=self.custom_y_trans_var, width=7,
                                        command=lambda: self.update_setting("common", "custom_y_translation", self.custom_y_trans_var.get(), True))
        self.custom_y_trans_var.trace_add("write", lambda *args: self.update_setting("common", "custom_y_translation", self.custom_y_trans_var.get(), True))
        self.custom_y_trans_spin.grid(row=custom_xy_row_start+3, column=1, sticky=tk.W, pady=1)
        
        self.custom_xy_widgets_controls = [ # Renamed from custom_xy_widgets
            self.custom_x_orig_spin, self.custom_y_orig_spin,
            self.custom_x_trans_spin, self.custom_y_trans_spin
        ]
        # Define labels for custom XY section
        self.custom_xy_widgets_labels = [
            parent_frame.grid_slaves(row=custom_xy_row_start, column=0)[0],      # Label for "主字幕 X:"
            parent_frame.grid_slaves(row=custom_xy_row_start+1, column=0)[0],  # Label for "主字幕 Y:"
            parent_frame.grid_slaves(row=custom_xy_row_start+2, column=0)[0],  # Label for "翻译字幕 X:"
            parent_frame.grid_slaves(row=custom_xy_row_start+3, column=0)[0]   # Label for "翻译字幕 Y:"
        ]
        # self.custom_xy_widgets_controls.extend(self.custom_xy_widgets_labels) # Labels are handled separately in toggle


        parent_frame.columnconfigure(1, weight=1)
        self.toggle_custom_xy_widgets() # Set initial state based on align_mode


    def create_text_style_ui(self, parent_frame, text_type: str): # text_type is "original" or "translation"
        row_idx = 0

        # Font Path
        ttk.Label(parent_frame, text="字体文件路径:").grid(row=row_idx, column=0, sticky=tk.W, pady=2)
        font_path_var = tk.StringVar(value=self.current_settings[text_type]["font_path"])
        ttk.Entry(parent_frame, textvariable=font_path_var, width=30).grid(row=row_idx, column=1, sticky=tk.EW, pady=2)
        ttk.Button(parent_frame, text="浏览字体...", 
                   command=lambda tt=text_type, fpv=font_path_var: self.browse_font_file(tt, fpv)).grid(row=row_idx, column=2, padx=5, pady=2)
        font_path_var.trace_add("write", lambda *args, tt=text_type, var=font_path_var: self.update_setting(tt, "font_path", var.get(), True))
        row_idx += 1

        # Font Size
        ttk.Label(parent_frame, text="字体大小:").grid(row=row_idx, column=0, sticky=tk.W, pady=2)
        font_size_var = tk.IntVar(value=self.current_settings[text_type]["font_size"])
        ttk.Spinbox(parent_frame, from_=8, to=200, textvariable=font_size_var, width=5,
                    command=lambda tt=text_type, var=font_size_var: self.update_setting(tt, "font_size", var.get(), True)).grid(row=row_idx, column=1, sticky=tk.W, pady=2)
        row_idx += 1

        # Font Color
        ttk.Label(parent_frame, text="字体颜色:").grid(row=row_idx, column=0, sticky=tk.W, pady=2)
        # Store color as (R,G,B,A) tuple, but display as hex for colorchooser
        initial_color_rgb = self.current_settings[text_type]["font_color"][:3] # Get RGB part
        initial_color_hex = f"#{initial_color_rgb[0]:02x}{initial_color_rgb[1]:02x}{initial_color_rgb[2]:02x}"
        
        color_button = ttk.Button(parent_frame, text=initial_color_hex, width=10,
                                 command=lambda tt=text_type: self.choose_color(tt))
        color_button.grid(row=row_idx, column=1, sticky=tk.W, pady=2)
        # We'll need to store the button reference to update its text if color changes
        setattr(self, f"{text_type}_color_button", color_button) 
        row_idx += 1
        
        # --- Effects ---
        effects_frame = ttk.LabelFrame(parent_frame, text="效果", padding="5")
        effects_frame.grid(row=row_idx, column=0, columnspan=3, sticky=tk.EW, pady=10)
        # row_idx +=1 # No, use internal row indexing for effects_frame

        effect_row = 0
        # --- Shadow Controls ---
        shadow_effects = self.current_settings[text_type]["effects"]
        
        shadow_on_var = tk.BooleanVar(value=shadow_effects.get("shadow_on", False))
        ttk.Checkbutton(effects_frame, text="启用阴影", variable=shadow_on_var,
                        command=lambda tt=text_type, var=shadow_on_var: self.update_effect_setting(tt, "shadow_on", var.get(), True)
                       ).grid(row=effect_row, column=0, sticky=tk.W, columnspan=1) # Span 1 to allow label next to it
        
        ttk.Label(effects_frame, text="X偏移:").grid(row=effect_row + 1, column=0, sticky=tk.W, padx=(20,0))
        shadow_x_var = tk.IntVar(value=shadow_effects.get("shadow_offset_x", 0))
        ttk.Spinbox(effects_frame, from_=-50, to=50, textvariable=shadow_x_var, width=5,
                    command=lambda tt=text_type, var=shadow_x_var: self.update_effect_setting(tt, "shadow_offset_x", var.get(), True)
                   ).grid(row=effect_row + 1, column=1, sticky=tk.W)

        ttk.Label(effects_frame, text="Y偏移:").grid(row=effect_row + 2, column=0, sticky=tk.W, padx=(20,0))
        shadow_y_var = tk.IntVar(value=shadow_effects.get("shadow_offset_y", 0))
        ttk.Spinbox(effects_frame, from_=-50, to=50, textvariable=shadow_y_var, width=5,
                    command=lambda tt=text_type, var=shadow_y_var: self.update_effect_setting(tt, "shadow_offset_y", var.get(), True)
                   ).grid(row=effect_row + 2, column=1, sticky=tk.W)

        ttk.Label(effects_frame, text="阴影颜色:").grid(row=effect_row + 3, column=0, sticky=tk.W, padx=(20,0))
        shadow_color_rgba = shadow_effects.get("shadow_color", (0,0,0,128))
        shadow_color_hex = f"#{shadow_color_rgba[0]:02x}{shadow_color_rgba[1]:02x}{shadow_color_rgba[2]:02x}"
        shadow_color_button = ttk.Button(effects_frame, text=shadow_color_hex, width=8,
                                     command=lambda tt=text_type: self.choose_effect_color(tt, "shadow_color"))
        shadow_color_button.grid(row=effect_row + 3, column=1, sticky=tk.W)
        setattr(self, f"{text_type}_shadow_color_button", shadow_color_button)
        # TODO: Add Alpha slider for shadow_color

        effect_row += 4 # Next effect starts after these 4 rows (0,1,2,3 for shadow)

        # --- Outline Controls ---
        outline_effects = self.current_settings[text_type]["effects"]

        outline_on_var = tk.BooleanVar(value=outline_effects.get("outline_on", False))
        ttk.Checkbutton(effects_frame, text="启用描边", variable=outline_on_var,
                        command=lambda tt=text_type, var=outline_on_var: self.update_effect_setting(tt, "outline_on", var.get(), True)
                       ).grid(row=effect_row, column=0, sticky=tk.W, columnspan=1)

        ttk.Label(effects_frame, text="宽度:").grid(row=effect_row + 1, column=0, sticky=tk.W, padx=(20,0))
        outline_width_var = tk.IntVar(value=outline_effects.get("outline_width", 0))
        ttk.Spinbox(effects_frame, from_=0, to=20, textvariable=outline_width_var, width=5,
                     command=lambda tt=text_type, var=outline_width_var: self.update_effect_setting(tt, "outline_width", var.get(), True)
                    ).grid(row=effect_row + 1, column=1, sticky=tk.W)
        
        ttk.Label(effects_frame, text="描边颜色:").grid(row=effect_row + 2, column=0, sticky=tk.W, padx=(20,0))
        outline_color_rgba = outline_effects.get("outline_color", (0,0,0,255))
        outline_color_hex = f"#{outline_color_rgba[0]:02x}{outline_color_rgba[1]:02x}{outline_color_rgba[2]:02x}"
        outline_color_button = ttk.Button(effects_frame, text=outline_color_hex, width=8,
                                     command=lambda tt=text_type: self.choose_effect_color(tt, "outline_color"))
        outline_color_button.grid(row=effect_row + 2, column=1, sticky=tk.W)
        setattr(self, f"{text_type}_outline_color_button", outline_color_button)
        # TODO: Add Alpha slider for outline_color
        effect_row += 3 # Next effect starts after these 3 rows for outline

        # --- Gradient Controls ---
        gradient_effects = self.current_settings[text_type]["effects"]
        
        gradient_on_var = tk.BooleanVar(value=gradient_effects.get("gradient_on", False))
        ttk.Checkbutton(effects_frame, text="启用渐变", variable=gradient_on_var,
                        command=lambda tt=text_type, var=gradient_on_var: self.update_effect_setting(tt, "gradient_on", var.get(), True)
                       ).grid(row=effect_row, column=0, sticky=tk.W, columnspan=1)

        ttk.Label(effects_frame, text="起始颜色:").grid(row=effect_row + 1, column=0, sticky=tk.W, padx=(20,0))
        gradient_start_rgba = gradient_effects.get("gradient_color_start", (255,0,0,255))
        gradient_start_hex = f"#{gradient_start_rgba[0]:02x}{gradient_start_rgba[1]:02x}{gradient_start_rgba[2]:02x}"
        gradient_start_button = ttk.Button(effects_frame, text=gradient_start_hex, width=8,
                                     command=lambda tt=text_type: self.choose_effect_color(tt, "gradient_color_start"))
        gradient_start_button.grid(row=effect_row + 1, column=1, sticky=tk.W)
        setattr(self, f"{text_type}_gradient_color_start_button", gradient_start_button)

        ttk.Label(effects_frame, text="结束颜色:").grid(row=effect_row + 2, column=0, sticky=tk.W, padx=(20,0))
        gradient_end_rgba = gradient_effects.get("gradient_color_end", (0,0,255,255))
        gradient_end_hex = f"#{gradient_end_rgba[0]:02x}{gradient_end_rgba[1]:02x}{gradient_end_rgba[2]:02x}"
        gradient_end_button = ttk.Button(effects_frame, text=gradient_end_hex, width=8,
                                     command=lambda tt=text_type: self.choose_effect_color(tt, "gradient_color_end"))
        gradient_end_button.grid(row=effect_row + 2, column=1, sticky=tk.W)
        setattr(self, f"{text_type}_gradient_color_end_button", gradient_end_button)
        # TODO: Add Alpha sliders for gradient colors
        # TODO: Add gradient direction (currently vertical only in renderer)

        effects_frame.columnconfigure(1, weight=1) # Allow spinboxes/buttons to take space
        parent_frame.columnconfigure(1, weight=1) # Ensure parent frame's column 1 also expands


    def browse_font_file(self, text_type: str, var_to_update: tk.StringVar):
        path = filedialog.askopenfilename(
            title=f"选择 {text_type} 字体文件",
            filetypes=(("Font files", "*.ttf *.otf *.ttc"), ("All files", "*.*"))
        )
        if path:
            var_to_update.set(path) # This will trigger the trace and update_setting

    def choose_color(self, text_type: str): # For main font color
        current_rgba = self.current_settings[text_type]["font_color"]
        current_rgb_hex = f"#{current_rgba[0]:02x}{current_rgba[1]:02x}{current_rgba[2]:02x}"
        
        new_color_tuple = colorchooser.askcolor(initialcolor=current_rgb_hex, title=f"选择 {text_type} 字体颜色")

        if new_color_tuple[0] is not None:
            r, g, b = [int(c) for c in new_color_tuple[0]]
            # TODO: Add Alpha slider for main font color, for now keep existing alpha
            new_rgba = (r, g, b, current_rgba[3])
            self.update_setting(text_type, "font_color", new_rgba, True)
            
            button_attr_name = f"{text_type}_color_button"
            if hasattr(self, button_attr_name):
                getattr(self, button_attr_name).config(text=new_color_tuple[1])

    def choose_effect_color(self, text_type: str, effect_key: str): # e.g., effect_key = "shadow_color"
        """Handles color selection for effect components like shadow or outline."""
        current_effect_rgba = self.current_settings[text_type]["effects"].get(effect_key, (0,0,0,255))
        current_effect_rgb_hex = f"#{current_effect_rgba[0]:02x}{current_effect_rgba[1]:02x}{current_effect_rgba[2]:02x}"

        title_map = {
            "shadow_color": "阴影颜色",
            "outline_color": "描边颜色",
            "gradient_color_start": "渐变起始颜色",
            "gradient_color_end": "渐变结束颜色"
        }
        dialog_title = f"选择 {text_type} {title_map.get(effect_key, '效果颜色')}"
        
        new_color_tuple = colorchooser.askcolor(initialcolor=current_effect_rgb_hex, title=dialog_title)

        if new_color_tuple[0] is not None:
            r, g, b = [int(c) for c in new_color_tuple[0]]
            # TODO: Add Alpha slider for effect colors, for now keep existing alpha or default
            default_alpha = 128 if "shadow" in effect_key else 255
            alpha = current_effect_rgba[3] if len(current_effect_rgba) == 4 else default_alpha
            new_rgba = (r, g, b, alpha)
            
            self.update_effect_setting(text_type, effect_key, new_rgba, True)
            
            button_attr_name = f"{text_type}_{effect_key}_button" # e.g. original_shadow_color_button
            if hasattr(self, button_attr_name):
                getattr(self, button_attr_name).config(text=new_color_tuple[1])
            else: # Fallback for buttons if not named exactly like this (e.g. if effect_key has no "_color")
                # This part might need adjustment based on actual button naming for effects
                simple_button_name = f"{text_type}_{effect_key.replace('_color','')}_color_button"
                if hasattr(self, simple_button_name):
                     getattr(self, simple_button_name).config(text=new_color_tuple[1])


    def update_setting(self, category: str, key: str, value, trigger_preview=False):
        """Updates a common setting or a direct text_type setting (font_path, font_size, font_color)."""
        if category == "common":
            self.current_settings["common"][key] = value
        else: # "original" or "translation"
            self.current_settings[category][key] = value
        
        if trigger_preview:
            # If a setting that affects layout (like resolution) changes,
            # it might be good to re-trigger main content resize logic if needed,
            # or just rely on update_preview to use new resolution.
            # For now, just update_preview.
            self.update_preview()
    
    def on_align_mode_change(self, event=None):
        new_mode = self.text_align_var.get()
        self.update_setting("common", "text_align", new_mode, False) # Update setting first
        self.toggle_custom_xy_widgets() # Then toggle UI elements
        self.update_preview() # Finally, trigger preview update

    def toggle_custom_xy_widgets(self):
        # Since X/Y inputs and line spacing are always enabled,
        # this method might not be needed for them anymore.
        # The "custom_xy" mode itself might be removed if left/center/right + XY suffice.
        # For now, let's assume all these controls are always NORMAL.
        
        # is_custom_mode = (self.text_align_var.get() == "custom_xy") # custom_xy might be removed
        # custom_state = tk.NORMAL # if is_custom_mode else tk.DISABLED
        # non_custom_state = tk.NORMAL # tk.DISABLED if is_custom_mode else tk.NORMAL

        # All X/Y and line spacing controls are now always enabled.
        for widget in self.custom_xy_widgets_controls: # Spinboxes for X/Y
            widget.config(state=tk.NORMAL)
        for widget in self.custom_xy_widgets_labels: # Labels for X/Y
            widget.config(state=tk.NORMAL) # ttk.Label supports state

        # Y offset controls and label are removed.
        # Line spacing controls and label are removed.


    def update_effect_setting(self, text_type: str, effect_key: str, value, trigger_preview=False):
        """Updates a specific key within the 'effects' dictionary for a text_type."""
        self.current_settings[text_type]["effects"][effect_key] = value
        if trigger_preview:
            self.update_preview()


    # def on_main_content_resize(self, event=None): ... # Removed as preview size is now fixed
    # def _perform_resize(self): ... # Removed as preview size is now fixed

    def update_preview_on_resize(self, event):
        # This is called when the preview_label widget is resized.
        self.update_preview()

    def get_full_render_settings(self) -> dict:
        """Combines common, original, and translation settings into one dict for the renderer."""
        full = self.current_settings["common"].copy()
        full["font_path_original"] = self.current_settings["original"]["font_path"]
        full["font_size_original"] = self.current_settings["original"]["font_size"]
        full["font_color_original"] = self.current_settings["original"]["font_color"]
        full["effects_original"] = self.current_settings["original"]["effects"].copy()
        
        full["font_path_translation"] = self.current_settings["translation"]["font_path"]
        full["font_size_translation"] = self.current_settings["translation"]["font_size"]
        full["font_color_translation"] = self.current_settings["translation"]["font_color"]
        full["effects_translation"] = self.current_settings["translation"]["effects"].copy()
        return full

    def update_preview(self):
        # Generate a preview image based on current settings
        # Use a sample text for preview
        preview_text_original = "示例文字 (Preview)"
        preview_text_translation = "サンプルテキスト (見本)"

        render_settings = self.get_full_render_settings()
        
        # Get target preview label size
        preview_label_width = self.preview_label.winfo_width()
        preview_label_height = self.preview_label.winfo_height()

        if preview_label_width <= 1 or preview_label_height <= 1: # Not yet drawn
            self.root.after(100, self.update_preview) # Try again shortly
            return

        try:
            # Render at full resolution first
            img_width_full, img_height_full = RESOLUTIONS[render_settings["resolution"]]
            
            # Create a temporary PIL Image for rendering
            pil_image_full = Image.new("RGBA", (img_width_full, img_height_full), (0,0,0,0))
            draw = ImageDraw.Draw(pil_image_full)
            
            font_orig = get_font(render_settings["font_path_original"], render_settings["font_size_original"])
            font_trans = get_font(render_settings["font_path_translation"], render_settings["font_size_translation"])

            # Calculate text sizes
            bbox_orig = draw.textbbox((0,0), preview_text_original, font=font_orig)
            text_w_orig = bbox_orig[2] - bbox_orig[0]
            text_h_orig = bbox_orig[3] - bbox_orig[1]

            align_setting = render_settings["text_align"]

            # User-defined X/Y are relative to screen bottom-left
            user_x_original = render_settings.get("custom_x_original", 0)
            user_y_original_bottom_edge = render_settings.get("custom_y_original", 0)

            # Pillow Y for original text (top_left)
            pil_y_orig_top_edge = img_height_full - user_y_original_bottom_edge - text_h_orig

            # Pillow X for original text (top_left)
            if align_setting == "left":
                pil_x_orig = user_x_original
            elif align_setting == "center":
                pil_x_orig = user_x_original - (text_w_orig / 2)
            elif align_setting == "right":
                pil_x_orig = user_x_original - text_w_orig
            else: # Default to left
                print(f"Preview Warning: Unknown text_align mode '{align_setting}', defaulting to left.")
                pil_x_orig = user_x_original
            
            x_orig, y_orig = pil_x_orig, pil_y_orig_top_edge
            x_trans, y_trans = 0, 0 # Initialize for translation

            if preview_text_translation:
                bbox_trans = draw.textbbox((0,0), preview_text_translation, font=font_trans)
                text_w_trans = bbox_trans[2] - bbox_trans[0]
                text_h_trans = bbox_trans[3] - bbox_trans[1]

                # line_spacing = render_settings.get("line_spacing", 10) # Line spacing removed
                user_x_translation = render_settings.get("custom_x_translation", 0)
                user_y_translation_bottom_edge = render_settings.get("custom_y_translation", 0) # Directly use this
                
                # Pillow Y for translation (top_left)
                pil_y_trans_top_edge = img_height_full - user_y_translation_bottom_edge - text_h_trans
                
                if align_setting == "left":
                    pil_x_trans = user_x_translation
                elif align_setting == "center":
                    pil_x_trans = user_x_translation - (text_w_trans / 2)
                elif align_setting == "right":
                    pil_x_trans = user_x_translation - text_w_trans
                else: # Default to left
                    pil_x_trans = user_x_translation
                
                x_trans, y_trans = pil_x_trans, pil_y_trans_top_edge
            
            # Using the more complex draw_text_with_effects from renderer.py would be better
            # For now, a simpler draw for speed in preview:
            from core.renderer import draw_text_with_effects # Import directly for preview
            draw_text_with_effects(draw, preview_text_original, (int(x_orig), int(y_orig)), font_orig, 
                                   render_settings["font_color_original"], render_settings["effects_original"])
            draw_text_with_effects(draw, preview_text_translation, (int(x_trans), int(y_trans)), font_trans, 
                                   render_settings["font_color_translation"], render_settings["effects_translation"])

            # pil_image_full now contains the full-resolution rendered subtitle text.

            # Determine target 16:9 display dimensions based on preview_label_width and preview_label_height
            aspect_ratio_16_9 = 16 / 9
            widget_aspect_ratio = preview_label_width / preview_label_height

            if widget_aspect_ratio > aspect_ratio_16_9: # Widget is wider than 16:9, height is the limit
                target_h = preview_label_height
                target_w = int(target_h * aspect_ratio_16_9)
            else: # Widget is taller or same aspect as 16:9, width is the limit
                target_w = preview_label_width
                target_h = int(target_w / aspect_ratio_16_9)
            
            target_w = max(1, target_w) # Ensure at least 1x1
            target_h = max(1, target_h)

            # Create a copy of the rendered content and thumbnail it to the target 16:9 display size
            img_for_display = pil_image_full.copy()
            img_for_display.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
            # Now img_for_display.width and .height are the actual 16:9 dimensions of the image to show.

            # Determine the base image for compositing: either user's background or checkerboard
            final_preview_width = img_for_display.width
            final_preview_height = img_for_display.height
            
            base_image_for_preview = Image.new("RGBA", (final_preview_width, final_preview_height))

            if self.preview_background_image_pil:
                # Scale user's background image to fit final_preview_width, final_preview_height (16:9)
                # This might crop or letterbox if user image is not 16:9. For simplicity, let's resize and center.
                # A better approach would be to scale to fill and then crop, or scale to fit and letterbox.
                # For now, just resize to the target dimensions.
                bg_resized = self.preview_background_image_pil.resize((final_preview_width, final_preview_height), Image.Resampling.LANCZOS)
                if bg_resized.mode != "RGBA": # Ensure it's RGBA for alpha_composite
                    bg_resized = bg_resized.convert("RGBA")
                base_image_for_preview = bg_resized
            else:
                # Create checkerboard background
                draw_base = ImageDraw.Draw(base_image_for_preview)
                checker_size = 20
                if final_preview_width < 40 or final_preview_height < 40: checker_size = 5
                elif final_preview_width < 100 or final_preview_height < 100: checker_size = 10

                for r_idx in range(0, final_preview_height, checker_size):
                    for c_idx in range(0, final_preview_width, checker_size):
                        fill_color = (200, 200, 200, 255) if (r_idx // checker_size + c_idx // checker_size) % 2 == 0 else (230, 230, 230, 255)
                        draw_base.rectangle([c_idx, r_idx, c_idx + checker_size, r_idx + checker_size], fill=fill_color)
            
            # Composite the (scaled) subtitle image onto the base image (background or checkerboard)
            # img_for_display is RGBA (text with transparent background)
            # base_image_for_preview is RGBA
            final_16_9_image = Image.alpha_composite(base_image_for_preview, img_for_display)
            
            self.preview_photo = ImageTk.PhotoImage(final_16_9_image)
            self.preview_label.config(image=self.preview_photo)

        except Exception as e:
            self.preview_label.config(image=None, text=f"预览错误:\n{e}") # Show error in label
            print(f"Preview error: {e}")
            import traceback
            traceback.print_exc()


    def start_generation_thread(self):
        if not self.subtitle_file_path.get():
            self.status_label.config(text="错误: 请先选择字幕文件!")
            return
        
        self.generate_button.config(state=tk.DISABLED)
        self.status_label.config(text="正在生成图片...")
        
        # Run generation in a separate thread to avoid freezing the GUI
        thread = threading.Thread(target=self.generate_images_task)
        thread.daemon = True # Allows main program to exit even if thread is running
        thread.start()

    def generate_images_task(self):
        sub_file = self.subtitle_file_path.get()
        render_settings = self.get_full_render_settings()
        render_settings["output_directory"] = self.output_directory.get() # Ensure latest output dir

        if not os.path.exists(render_settings["output_directory"]):
            try:
                os.makedirs(render_settings["output_directory"])
            except OSError as e:
                self.root.after(0, lambda: self.status_label.config(text=f"错误: 创建输出目录失败 - {e}"))
                self.root.after(0, lambda: self.generate_button.config(state=tk.NORMAL))
                return

        parsed_entries: list[SubtitleEntry] = parse_subtitle_file(sub_file)
        total_entries = len(parsed_entries)
        
        if not parsed_entries:
            self.root.after(0, lambda: self.status_label.config(text="未找到有效字幕或解析错误。"))
            self.root.after(0, lambda: self.generate_button.config(state=tk.NORMAL))
            return

        for i, entry in enumerate(parsed_entries):
            original_text = entry.get("original_text")
            if not original_text:
                continue

            # Construct the filename base from the original text only.
            # Tags will be passed separately to the renderer.
            base_filename = sanitize_filename(original_text)

            current_tags = []
            if 'full_tag_original' in entry and entry['full_tag_original']:
                current_tags.append(entry['full_tag_original'])
            # Add other potential tags if necessary, similar to main.py

            tag_prefix_for_status = ""
            if current_tags:
                tag_prefix_for_status = " ".join([f"[{tag}]" for tag in current_tags]) + " "
            
            status_msg = f"正在生成 ({i+1}/{total_entries}): {tag_prefix_for_status}{base_filename}.png"
            self.root.after(0, lambda msg=status_msg: self.status_label.config(text=msg))

            render_subtitle_image(
                original_text=original_text,
                translated_text=entry.get("translated_text"),
                filename_base=base_filename, # Now only sanitized text content
                tags=current_tags,           # Pass the extracted tags
                settings=render_settings
            )
        
        self.root.after(0, lambda: self.status_label.config(text=f"完成! {total_entries} 张图片已生成到 '{render_settings['output_directory']}'"))
        self.root.after(0, lambda: self.generate_button.config(state=tk.NORMAL))


if __name__ == '__main__':
    root = tk.Tk()
    app = SubtitleApp(root)
    root.mainloop()