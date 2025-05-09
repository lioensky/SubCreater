from PIL import Image, ImageDraw, ImageFont
from typing import Tuple, Optional, Dict, Any
import os

# Default settings (can be overridden by GUI later)
DEFAULT_SETTINGS = {
    "resolution": "1080p",
    "font_path_original": "arial.ttf",
    "font_size_original": 60,
    "font_color_original": (255, 255, 0, 255), # Yellow, RGBA
    "font_path_translation": "arial.ttf",
    "font_size_translation": 40,
    "font_color_translation": (220, 220, 220, 255), # Light Gray, RGBA
    
    # Alignment and Position
    "text_align": "center", # "left", "center", "right", "custom_xy"
    "position_y_offset": -100,  # Offset from bottom for non-custom_xy modes
    "line_spacing": 10, # Space between original and translation for non-custom_xy modes
    
    # Custom XY coordinates (used if text_align is "custom_xy")
    # These are for the top-left of the text bounding box.
    "custom_x_original": 640, # Example for 1080p center-ish
    "custom_y_original": 800, # Example for 1080p bottom-ish
    "custom_x_translation": 640,
    "custom_y_translation": 880,

    "output_directory": "output_images",
    "effects_original": {
        "shadow_on": True,
        "shadow_offset_x": 3,
        "shadow_offset_y": 3,
        "shadow_color": (0, 0, 0, 128),
        "outline_on": True,
        "outline_width": 2,
        "outline_color": (0, 0, 0, 255),
        "gradient_on": False,
        "gradient_color_start": (255, 105, 180, 255), # Hot Pink
        "gradient_color_end": (255, 255, 255, 255),   # White
        "gradient_direction": "vertical"
    },
    "effects_translation": {
        "shadow_on": True,
        "shadow_offset_x": 2,
        "shadow_offset_y": 2,
        "shadow_color": (0, 0, 0, 128),
        "outline_on": True,
        "outline_width": 1,
        "outline_color": (0, 0, 0, 255),
        "gradient_on": False,
        "gradient_color_start": (200, 200, 200, 255), # Light Gray
        "gradient_color_end": (250, 250, 250, 255),   # Lighter Gray
        "gradient_direction": "vertical"
    }
}

RESOLUTIONS = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
}

def get_font(font_path: str, font_size: int) -> ImageFont.FreeTypeFont:
    """Loads a font. Tries a few common locations if direct path fails."""
    try:
        return ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Warning: Font not found at '{font_path}'. Trying system default 'arial.ttf'.")
        try:
            return ImageFont.truetype("arial.ttf", font_size) # Common on Windows
        except IOError:
            print(f"Warning: 'arial.ttf' not found. Trying 'DejaVuSans.ttf'.")
            try:
                return ImageFont.truetype("DejaVuSans.ttf", font_size) # Common on Linux
            except IOError:
                print("Error: Could not load a default font. Please specify a valid font_path.")
                raise

def draw_text_with_effects(
    draw: ImageDraw.ImageDraw,
    text: str,
    position: Tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill_color: Tuple[int, int, int, int],
    effects: Dict[str, Any]
):
    """
    Draws text with optional outline and shadow.
    Basic implementation. More advanced effects might require more complex logic.
    """
    x, y = position

    # Outline
    if effects.get("outline_on", False) and effects.get("outline_width", 0) > 0:
        outline_w = effects["outline_width"]
        outline_c = effects.get("outline_color", (0, 0, 0, 255)) # Default to black if not specified
        # Ensure outline_c has alpha if it's RGB
        if len(outline_c) == 3:
            outline_c = outline_c + (255,)

        for dx_outline in range(-outline_w, outline_w + 1):
            for dy_outline in range(-outline_w, outline_w + 1):
                # Simple square outline, for circular: if dx_outline*dx_outline + dy_outline*dy_outline <= outline_w*outline_w:
                if abs(dx_outline) == outline_w or abs(dy_outline) == outline_w or \
                   (abs(dx_outline) < outline_w and abs(dy_outline) < outline_w and \
                    (dx_outline*dx_outline + dy_outline*dy_outline >= (outline_w-1)*(outline_w-1))): # Fill center for thicker outlines
                     draw.text((x + dx_outline, y + dy_outline), text, font=font, fill=outline_c)
    
    # Shadow
    if effects.get("shadow_on", False):
        shadow_offset_x = effects.get("shadow_offset_x", 0)
        shadow_offset_y = effects.get("shadow_offset_y", 0)
        shadow_c = effects.get("shadow_color", (0, 0, 0, 128)) # Default to semi-transparent black
        # Ensure shadow_c has alpha if it's RGB
        if len(shadow_c) == 3:
            shadow_c = shadow_c + (128,) # Default alpha for shadow if not provided

        if shadow_offset_x != 0 or shadow_offset_y != 0: # Only draw if there's an offset
            draw.text((x + shadow_offset_x, y + shadow_offset_y), text, font=font, fill=shadow_c)

    # Main text
    if effects.get("gradient_on", False):
        # Get gradient parameters
        color_start = effects.get("gradient_color_start", (255,0,0,255)) # Default Red
        color_end = effects.get("gradient_color_end", (0,0,255,255))     # Default Blue
        # direction = effects.get("gradient_direction", "vertical") # Vertical only for now

        # Ensure colors have alpha
        if len(color_start) == 3: color_start += (255,)
        if len(color_end) == 3: color_end += (255,)

        # Determine text bounding box to create appropriately sized temp images
        # draw.textbbox((0,0)...) gives bbox relative to (0,0) if text were drawn there
        # For text at `position=(x,y)`, its actual bbox on the main image is offset by x,y.
        # We need the size of the text itself, and its internal offsets.
        try:
            # For Pillow >= 9.2.0, textbbox is preferred.
            # The xy for textbbox should be (0,0) to get the text's own metrics.
            text_bbox = draw.textbbox((0,0), text, font=font)
        except AttributeError:
            # Fallback for older Pillow versions
            text_size = draw.textsize(text, font=font)
            text_bbox = (0, 0, text_size[0], text_size[1]) # Assuming top-left origin for textsize

        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        # text_offset_x, text_offset_y are how much the drawn text's top-left
        # is offset from the (0,0) point *within its own bounding box*.
        # This is important for drawing into the mask at its (0,0).
        text_internal_offset_x = text_bbox[0]
        text_internal_offset_y = text_bbox[1]

        if text_width <= 0 or text_height <= 0: # Nothing to draw
            return

        # 1. Create text mask
        mask_image = Image.new('L', (text_width, text_height), 0) # 'L' mode for alpha mask
        mask_draw = ImageDraw.Draw(mask_image)
        # Draw text onto mask at its internal top-left (adjusting for internal offsets)
        mask_draw.text((-text_internal_offset_x, -text_internal_offset_y), text, font=font, fill=255)

        # 2. Create gradient image
        gradient_image = Image.new('RGBA', (text_width, text_height))
        gradient_draw = ImageDraw.Draw(gradient_image)

        for i in range(text_height): # Vertical gradient
            ratio = i / max(1, text_height -1) # Avoid division by zero for 1px height
            r = int(color_start[0] * (1 - ratio) + color_end[0] * ratio)
            g = int(color_start[1] * (1 - ratio) + color_end[1] * ratio)
            b = int(color_start[2] * (1 - ratio) + color_end[2] * ratio)
            a = int(color_start[3] * (1 - ratio) + color_end[3] * ratio)
            gradient_draw.line([(0, i), (text_width, i)], fill=(r, g, b, a))
        
        # 3. Composite onto main image
        # The `position` (x,y) is where the top-left of the text's bounding box should be placed.
        # So, we paste our `gradient_image` (which is sized to the bbox) at `position`,
        # but we need to account for the text's internal offset if the bbox itself starts at non-zero.
        # The paste position should be where the (0,0) of the text_bbox would land.
        paste_x = position[0] + text_internal_offset_x
        paste_y = position[1] + text_internal_offset_y
        
        # Get the main image object from the draw context
        main_image_obj = draw.im
        # Define the box as a 4-tuple: (left, top, right, bottom)
        # where right = left + width, and bottom = top + height.
        box = (paste_x, paste_y, paste_x + text_width, paste_y + text_height)
        # Try passing the core imaging object of the mask if Image object itself is not accepted.
        # mask_image is already 'L' mode.
        # Also try passing the core imaging object for the source image.
        main_image_obj.paste(gradient_image.im, box, mask_image.im)

    else: # Solid color text
        draw.text(position, text, font=font, fill=fill_color)


def render_subtitle_image(
    original_text: str,
    translated_text: Optional[str] = None,
    filename_base: str = "subtitle",
    settings: Dict[str, Any] = None
) -> Optional[str]:
    """
    Renders a single subtitle (one or two lines) onto a transparent PNG.

    Args:
        original_text: The main subtitle text.
        translated_text: Optional translated text (appears below original).
        filename_base: Base name for the output PNG file.
        settings: Dictionary of rendering settings. Uses DEFAULT_SETTINGS if None.

    Returns:
        Path to the generated image file, or None if an error occurred.
    """
    current_settings = DEFAULT_SETTINGS.copy()
    if settings:
        current_settings.update(settings)

    try:
        img_width, img_height = RESOLUTIONS[current_settings["resolution"]]
        image = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0)) # Transparent background
        draw = ImageDraw.Draw(image)

        font_original = get_font(current_settings["font_path_original"], current_settings["font_size_original"])
        font_translation = get_font(current_settings["font_path_translation"], current_settings["font_size_translation"])

        # Calculate text sizes
        # For Pillow < 9.2.0, use draw.textsize. For >= 9.2.0, use font.getbbox or draw.textbbox
        # Using textbbox as it's more accurate for positioning.
        # bbox is (left, top, right, bottom) relative to (0,0) for the text.
        # width = right - left, height = bottom - top.
        # top is usually negative for fonts with descenders below baseline.
        
        bbox_original = draw.textbbox((0,0), original_text, font=font_original)
        text_width_original = bbox_original[2] - bbox_original[0]
        text_height_original = bbox_original[3] - bbox_original[1]

        align_mode = current_settings["text_align"]
        # padding = 50 # Padding is no longer used as X is explicit

        # User-defined X/Y are relative to screen bottom-left
        user_x_original = current_settings.get("custom_x_original", 0)
        user_y_original_bottom_edge = current_settings.get("custom_y_original", 0) # This is the Y of the bottom edge of original text

        # Calculate Pillow's Y coordinate (top_left of text) for original text
        # Pillow Y = image_height - user_bottom_Y - text_height
        pil_y_original_top_edge = img_height - user_y_original_bottom_edge - text_height_original

        # Calculate Pillow's X coordinate (top_left of text) for original text based on align_mode
        if align_mode == "left":
            pil_x_original = user_x_original
        elif align_mode == "center":
            pil_x_original = user_x_original - (text_width_original / 2)
        elif align_mode == "right":
            pil_x_original = user_x_original - text_width_original
        else: # Default to left if unknown, or handle custom_xy if re-added
            print(f"Warning: Unknown text_align mode '{align_mode}', defaulting to left.")
            pil_x_original = user_x_original
            # If custom_xy mode is re-added, its X logic might be different (e.g., user_x_original is already top-left)
            # if align_mode == "custom_xy":
            #     pil_x_original = user_x_original # Assuming custom_x is top-left for custom_xy

        # Initialize translation positions
        pil_x_translation, pil_y_translation_top_edge = 0, 0

        if translated_text:
            bbox_translation = draw.textbbox((0,0), translated_text, font=font_translation)
            text_width_translation = bbox_translation[2] - bbox_translation[0]
            text_height_translation = bbox_translation[3] - bbox_translation[1]
            
            # line_spacing = current_settings.get("line_spacing", 10) # Line spacing is removed
            user_x_translation = current_settings.get("custom_x_translation", 0)
            user_y_translation_bottom_edge = current_settings.get("custom_y_translation", 0) # Directly use this

            # Pillow Y for translation (top_left of text)
            # Pillow Y = image_height - user_bottom_Y - text_height
            pil_y_translation_top_edge = img_height - user_y_translation_bottom_edge - text_height_translation


            if align_mode == "left":
                pil_x_translation = user_x_translation
            elif align_mode == "center":
                pil_x_translation = user_x_translation - (text_width_translation / 2)
            elif align_mode == "right":
                pil_x_translation = user_x_translation - text_width_translation
            else: # Default to left
                print(f"Warning: Unknown text_align mode '{align_mode}' for translation, defaulting to left.")
                pil_x_translation = user_x_translation
                # if align_mode == "custom_xy":
                #     pil_x_translation = user_x_translation # Assuming custom_x is top-left for custom_xy
        
        # For clarity in draw_text_with_effects calls
        x_original, y_pos_original = pil_x_original, pil_y_original_top_edge
        x_translation, y_pos_translation = pil_x_translation, pil_y_translation_top_edge
        
        # Perform drawing
        draw_text_with_effects(draw, original_text, (int(x_original), int(y_pos_original)), font_original,
                               current_settings["font_color_original"], current_settings.get("effects_original", {}))
        
        if translated_text:
            # For custom_xy, x_translation and y_pos_translation are already set.
            # For other modes, they were set inside the 'if translated_text:' block above.
            draw_text_with_effects(draw, translated_text, (int(x_translation), int(y_pos_translation)), font_translation,
                                   current_settings["font_color_translation"], current_settings.get("effects_translation", {}))

        output_dir = current_settings["output_directory"]
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        output_filepath = os.path.join(output_dir, f"{filename_base}.png")
        image.save(output_filepath)
        return output_filepath

    except FileNotFoundError as e: # Specifically for font files not found by get_font
        print(f"Rendering Error: Font file not found. {e}")
        return None
    except Exception as e:
        print(f"An error occurred during rendering {filename_base}.png: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    print("Renderer Test Script")
    # Test 1: Single line
    print("\nTest 1: Single line subtitle")
    settings_test1 = DEFAULT_SETTINGS.copy()
    # settings_test1["font_path_original"] = "C:/Windows/Fonts/msyh.ttc" # Example for Chinese
    # settings_test1["font_path_original"] = "simsun.ttc" # Another common Chinese font
    
    # To test with a specific font, uncomment and set the path below:
    # For example, if you have "NotoSansJP-Regular.otf" in the same directory as renderer.py
    # test_font_path = "NotoSansJP-Regular.otf" 
    # if os.path.exists(test_font_path):
    #    settings_test1["font_path_original"] = test_font_path
    #    settings_test1["font_path_translation"] = test_font_path
    # else:
    #    print(f"Test font {test_font_path} not found, using default.")

    path1 = render_subtitle_image(
        original_text="Hello World! This is a test.",
        filename_base="test_single_line",
        settings=settings_test1
    )
    if path1:
        print(f"Generated: {path1}")

    # Test 2: Dual line (original + translation)
    print("\nTest 2: Dual line subtitle")
    path2 = render_subtitle_image(
        original_text="Welcome to the Subtitle Generator",
        translated_text="欢迎使用字幕生成器",
        filename_base="test_dual_line",
        settings=settings_test1 # Using same settings, but font might need to support Chinese
    )
    if path2:
        print(f"Generated: {path2}")

    # Test 3: Different alignment
    print("\nTest 3: Left aligned")
    settings_test3 = settings_test1.copy()
    settings_test3["text_align"] = "left"
    path3 = render_subtitle_image(
        original_text="Left Aligned Text",
        translated_text="左对齐文本",
        filename_base="test_left_aligned",
        settings=settings_test3
    )
    if path3:
        print(f"Generated: {path3}")
    
    # Test 4: 720p
    print("\nTest 4: 720p resolution")
    settings_test4 = settings_test1.copy()
    settings_test4["resolution"] = "720p"
    settings_test4["font_size_original"] = 40
    settings_test4["font_size_translation"] = 30
    path4 = render_subtitle_image(
        original_text="720p Resolution Test",
        translated_text="720p 分辨率测试",
        filename_base="test_720p",
        settings=settings_test4
    )
    if path4:
        print(f"Generated: {path4}")

    print("\nRendering tests complete. Check the 'output_images' directory.")
    print("Note: If you see squares or incorrect characters, ensure the font specified in DEFAULT_SETTINGS")
    print(" (or overridden in tests) supports the characters being rendered (e.g., Chinese, Japanese).")
    print("You may need to change 'font_path_original' and 'font_path_translation' to a font file")
    print("available on your system that has the necessary glyphs, e.g., 'msyh.ttc' (Microsoft YaHei) or 'simsun.ttc' for Chinese on Windows.")