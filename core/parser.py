import re
from typing import List, Dict, Optional, Tuple

# Define a type alias for a subtitle entry for clarity
SubtitleEntry = Dict[str, Optional[str]]

def parse_subtitle_line(line: str) -> Optional[Tuple[str, str, str, bool]]:
    """
    Parses a single line of a subtitle file.
    Expected formats:
    [Tag]Text  (e.g., [Sub1]Hello World)
    [Tagch]Text (e.g., [Sub1ch]你好世界)

    Returns:
        A tuple (base_tag, full_tag, text, is_translation) or None if the line is invalid/empty.
        base_tag: e.g., "Sub1"
        full_tag: e.g., "Sub1" or "Sub1ch"
        text: The actual subtitle text.
        is_translation: True if the tag ends with "ch".
    """
    line = line.strip()
    if not line:
        return None

    match = re.match(r"\[([^\]]+)\](.*)", line)
    if not match:
        return None # Line does not conform to [Tag]Text format

    full_tag = match.group(1)
    text = match.group(2).strip()

    if not text: # If text part is empty after tag
        return None

    is_translation = full_tag.endswith("ch")
    base_tag = full_tag[:-2] if is_translation else full_tag

    return base_tag, full_tag, text, is_translation


def parse_subtitle_file(filepath: str) -> List[SubtitleEntry]:
    """
    Parses a subtitle file and groups original and translated lines.

    Args:
        filepath: Path to the subtitle file.

    Returns:
        A list of dictionaries, where each dictionary represents a subtitle
        to be rendered. Each dictionary has 'id', 'original_text',
        and optionally 'translated_text'.
        Example:
        [
            {'id': 'Sub1', 'original_text': 'Hello', 'translated_text': '你好'},
            {'id': 'Sub2', 'original_text': 'World', 'translated_text': None},
        ]
    """
    subtitles: List[SubtitleEntry] = []
    last_base_tag: Optional[str] = None
    temp_original_text: Optional[str] = None
    temp_full_tag_original: Optional[str] = None # Store the full tag of the original line

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_number, line_content in enumerate(f, 1):
                parsed_line = parse_subtitle_line(line_content)

                if not parsed_line:
                    # If there was a pending original text, it means it didn't have a translation
                    if temp_original_text and last_base_tag and temp_full_tag_original:
                        subtitles.append({
                            "id": last_base_tag,
                            "full_tag_original": temp_full_tag_original,
                            "original_text": temp_original_text,
                            "translated_text": None,
                            "full_tag_translation": None
                        })
                        temp_original_text = None
                        last_base_tag = None
                        temp_full_tag_original = None
                    continue # Skip empty or malformed lines

                base_tag, full_tag, text, is_translation = parsed_line

                if not is_translation:
                    # This is an original language line
                    # If there was a pending original text, finalize it (it didn't have a 'ch' pair)
                    if temp_original_text and last_base_tag and temp_full_tag_original:
                        subtitles.append({
                            "id": last_base_tag,
                            "full_tag_original": temp_full_tag_original,
                            "original_text": temp_original_text,
                            "translated_text": None,
                            "full_tag_translation": None
                        })
                    
                    # Store current line as a potential start of a new pair
                    temp_original_text = text
                    last_base_tag = base_tag
                    temp_full_tag_original = full_tag
                else:
                    # This is a translation line
                    if temp_original_text and last_base_tag == base_tag and temp_full_tag_original:
                        # It matches the pending original text
                        subtitles.append({
                            "id": base_tag,
                            "full_tag_original": temp_full_tag_original,
                            "original_text": temp_original_text,
                            "translated_text": text,
                            "full_tag_translation": full_tag
                        })
                        temp_original_text = None # Clear pending
                        last_base_tag = None
                        temp_full_tag_original = None
                    else:
                        # This 'ch' line doesn't have a matching original line immediately preceding it
                        # Or, it's an orphaned translation. We could log a warning or handle as an error.
                        # For now, we'll treat it as a single line subtitle with its 'ch' tag.
                        # This behavior might need refinement based on stricter rules.
                        # Or, more simply, we can choose to ignore orphaned translations.
                        # Let's ignore orphaned 'ch' lines for now, as per problem description
                        # which implies pairs or single non-'ch' lines.
                        # If we wanted to include them:
                        # subtitles.append({
                        #     "id": base_tag, # or full_tag if we want to keep 'ch'
                        #     "full_tag_original": full_tag, # Treat as original
                        #     "original_text": text,
                        #     "translated_text": None,
                        #     "full_tag_translation": None
                        # })
                        print(f"Warning: Orphaned translation or mismatched tag at line {line_number}: {line_content.strip()}")
                        pass # Ignoring orphaned translation

            # After loop, check if there's a pending original text without translation
            if temp_original_text and last_base_tag and temp_full_tag_original:
                subtitles.append({
                    "id": last_base_tag,
                    "full_tag_original": temp_full_tag_original,
                    "original_text": temp_original_text,
                    "translated_text": None,
                    "full_tag_translation": None
                })

    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return []
    except Exception as e:
        print(f"An error occurred while parsing {filepath}: {e}")
        return []

    return subtitles

if __name__ == '__main__':
    # Create a dummy subtitle file for testing
    dummy_file_content = """
[Sub1]Hello World
[Sub1ch]你好，世界
[Sub2]This is a test.
[Sub3]Another line.
[Sub3ch]另一行。
[Sub4]
[Sub5]Only original.
[InvalidLine]
[Sub6ch]Orphaned Translation
[Sub7]Followed by empty line then next sub

[Sub8]Final Sub
[Sub8ch]最后的字幕
"""
    dummy_filepath = "dummy_subs.txt"
    with open(dummy_filepath, "w", encoding="utf-8") as f:
        f.write(dummy_file_content)

    parsed_data = parse_subtitle_file(dummy_filepath)
    for i, entry in enumerate(parsed_data):
        print(f"Entry {i+1}:")
        print(f"  ID: {entry['id']}")
        print(f"  Original Tag: {entry['full_tag_original']}")
        print(f"  Original: {entry['original_text']}")
        if entry['translated_text']:
            print(f"  Translation Tag: {entry['full_tag_translation']}")
            print(f"  Translation: {entry['translated_text']}")
        print("-" * 20)

    # Test with a non-existent file
    print("\nTesting with non-existent file:")
    parse_subtitle_file("non_existent_file.txt")