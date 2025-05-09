import argparse
import os
from typing import Optional, List, Dict # Added Optional, List, Dict
from core.parser import parse_subtitle_file, SubtitleEntry # SubtitleEntry might need List/Dict from typing if it uses them internally in its definition for type hints.
from core.renderer import render_subtitle_image, DEFAULT_SETTINGS
from core.utils import sanitize_filename

def process_subtitles(subtitle_filepath: str, custom_settings: Optional[Dict] = None): # Changed dict to Dict
    """
    Processes a subtitle file: parses it and renders each entry as an image.
    """
    if not os.path.exists(subtitle_filepath):
        print(f"Error: Subtitle file not found at '{subtitle_filepath}'")
        return

    print(f"Parsing subtitle file: {subtitle_filepath}")
    parsed_entries: List[SubtitleEntry] = parse_subtitle_file(subtitle_filepath)

    if not parsed_entries:
        print("No valid subtitle entries found or an error occurred during parsing.")
        return

    output_dir = (custom_settings or DEFAULT_SETTINGS).get("output_directory", "output_images")
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")
        except OSError as e:
            print(f"Error creating output directory {output_dir}: {e}")
            return
            
    print(f"Found {len(parsed_entries)} subtitle entries. Starting rendering to '{output_dir}'...")

    # Prepare settings for renderer
    render_settings = DEFAULT_SETTINGS.copy()
    if custom_settings:
        # Deep merge for effects if present
        if "effects_original" in custom_settings and "effects_original" in render_settings:
            render_settings["effects_original"].update(custom_settings["effects_original"])
            del custom_settings["effects_original"] # Avoid shallow update for this key
        if "effects_translation" in custom_settings and "effects_translation" in render_settings:
            render_settings["effects_translation"].update(custom_settings["effects_translation"])
            del custom_settings["effects_translation"] # Avoid shallow update for this key
        render_settings.update(custom_settings)


    for i, entry in enumerate(parsed_entries):
        original_text = entry.get("original_text")
        if not original_text:
            print(f"Skipping entry {i+1} due to missing original text.")
            continue

        # Use the original text (after tag removal) for the filename base
        # The tag itself (like [Sub1]) is in entry['id'] or entry['full_tag_original']
        # The problem description implies filename from text: "[Sub1]第一句歌词.png"
        # So, we should use the full_tag_original + original_text for sanitization.
        
        # Construct the string that represents the subtitle line for filename generation
        # If [Sub1]Hello, then filename base is "Sub1_Hello"
        # If [Sub1]Hello and [Sub1ch]你好, filename base is still "Sub1_Hello"
        # The sanitize_filename function expects the tag as part of the input string.
        filename_source_text = f"[{entry['full_tag_original']}]{original_text}"
        
        base_filename = sanitize_filename(filename_source_text)
        
        print(f"Rendering '{base_filename}.png'...")
        
        output_path = render_subtitle_image(
            original_text=original_text,
            translated_text=entry.get("translated_text"),
            filename_base=base_filename,
            settings=render_settings
        )

        if output_path:
            print(f"Successfully generated: {output_path}")
        else:
            print(f"Failed to generate image for: {original_text}")

    print("Subtitle processing complete.")

def main():
    parser = argparse.ArgumentParser(description="Advanced Subtitle Layer Generator CLI")
    parser.add_argument("subtitle_file", help="Path to the subtitle file (.txt)")
    parser.add_argument("--resolution", choices=["720p", "1080p"], help="Output resolution (e.g., 1080p)")
    parser.add_argument("--font_original", help="Path to font file for original text")
    parser.add_argument("--font_size_original", type=int, help="Font size for original text")
    parser.add_argument("--font_color_original", help="Font color for original text (R,G,B,A e.g., 255,255,0,255)")
    parser.add_argument("--font_translation", help="Path to font file for translated text")
    parser.add_argument("--font_size_translation", type=int, help="Font size for translated text")
    parser.add_argument("--font_color_translation", help="Font color for translated text (R,G,B,A e.g., 220,220,220,255)")
    parser.add_argument("--output_dir", help="Directory to save generated PNG files")
    # Add more arguments for other settings as needed (e.g., shadow, outline)

    args = parser.parse_args()

    cli_settings = {}
    if args.resolution:
        cli_settings["resolution"] = args.resolution
    if args.font_original:
        cli_settings["font_path_original"] = args.font_original
    if args.font_size_original:
        cli_settings["font_size_original"] = args.font_size_original
    if args.font_color_original:
        try:
            cli_settings["font_color_original"] = tuple(map(int, args.font_color_original.split(',')))
            if len(cli_settings["font_color_original"]) != 4: raise ValueError
        except ValueError:
            print("Error: Invalid font_color_original format. Use R,G,B,A (e.g., 255,255,0,255)")
            return
    if args.font_translation:
        cli_settings["font_path_translation"] = args.font_translation
    if args.font_size_translation:
        cli_settings["font_size_translation"] = args.font_size_translation
    if args.font_color_translation:
        try:
            cli_settings["font_color_translation"] = tuple(map(int, args.font_color_translation.split(',')))
            if len(cli_settings["font_color_translation"]) != 4: raise ValueError
        except ValueError:
            print("Error: Invalid font_color_translation format. Use R,G,B,A (e.g., 220,220,220,255)")
            return
    if args.output_dir:
        cli_settings["output_directory"] = args.output_dir
    
    # Create a dummy subtitle file for quick testing if no file is provided and we are in a test mode
    # For now, we require the subtitle_file argument.
    # Example of how to run:
    # python main.py "path/to/your/subs.txt" --font_original "C:/Windows/Fonts/msyh.ttc" --font_translation "C:/Windows/Fonts/msyh.ttc"

    process_subtitles(args.subtitle_file, cli_settings)

if __name__ == "__main__":
    # Create a dummy subtitle file for testing main.py directly
    # This is helpful for development before GUI is ready.
    test_sub_content = """
[Intro1]Welcome to the Show!
[Intro1ch]欢迎来到表演现场！
[Verse1]This is the first verse.
[Chorus1]Singing the chorus loudly.
[Chorus1ch]大声歌唱副歌。
[Outro]The End.
    """
    test_sub_filepath = "sample_lyrics.txt"
    with open(test_sub_filepath, "w", encoding="utf-8") as f:
        f.write(test_sub_content)
    print(f"Created a sample subtitle file: {test_sub_filepath}")
    print("You can run the script like this:")
    print(f"python main.py {test_sub_filepath}")
    print("Or with custom fonts (example for Windows with Microsoft YaHei):")
    print(f"python main.py {test_sub_filepath} --font_original \"C:/Windows/Fonts/msyh.ttc\" --font_translation \"C:/Windows/Fonts/msyh.ttc\"")
    
    # To run automatically for testing:
    # main() # This would parse arguments from command line.
    # For an internal test call:
    # process_subtitles(test_sub_filepath, {"font_path_original": "msyh.ttc", "font_path_translation": "msyh.ttc"})
    # The above line assumes 'msyh.ttc' is findable by Pillow or in the same directory.
    # Better to run via CLI as intended.
    main()