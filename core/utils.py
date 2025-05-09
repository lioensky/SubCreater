import re

def sanitize_filename(text: str) -> str:
    """
    Sanitizes a string to be used as a filename.
    Removes or replaces characters that are not allowed in Windows filenames.
    Also removes the initial tag like [Sub1] or [Sub1ch].

    Args:
        text: The input string, potentially a line from a subtitle file
              e.g., "[Sub1]Hello World" or "Hello World" if tag is pre-stripped.

    Returns:
        A sanitized string suitable for use as a filename.
    """
    # Remove the tag if present (e.g., [Sub1], [Sub1ch])
    name_part = re.sub(r"^\[[^\]]+\]", "", text).strip()

    if not name_part: # If only tag was present or empty after stripping
        # Create a generic name if the text part is empty after stripping tag
        # This might happen for lines that are just tags or malformed.
        # Or, we might want to raise an error or return None,
        # depending on how the caller wants to handle this.
        # For now, let's use a placeholder.
        return "untitled_subtitle"

    # Remove characters that are illegal in Windows filenames
    # Illegal characters: < > : " / \ | ? *
    # Also, control characters (0-31)
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name_part)

    # Replace multiple spaces with a single underscore
    sanitized = re.sub(r'\s+', '_', sanitized)

    # Truncate if too long (Windows max path is 260, filename part usually shorter)
    # Let's cap at 100 characters for safety, can be adjusted.
    max_len = 100
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len]

    # If the name becomes empty after sanitization (e.g., "???"), provide a default
    if not sanitized:
        return "sanitized_empty_subtitle"

    return sanitized

if __name__ == '__main__':
    test_cases = [
        "[Sub1]Hello / World?*",
        "[Sub2ch]你好：世界<|>\\",
        "Just Text No Tag",
        "[EmptySub]",
        "  leading and trailing spaces  ",
        "very_long_filename_"*10 + "extra",
        "???",
        "A [bracketed] word" # Brackets in text, not as tag
    ]
    for tc in test_cases:
        tag_removed_for_filename = re.sub(r"^\[[^\]]+\]", "", tc).strip()
        print(f"Original: '{tc}' -> Text for filename: '{tag_removed_for_filename}' -> Sanitized: '{sanitize_filename(tc)}.png'")

    # Example of how it might be used with pre-stripped text
    print(f"Pre-stripped: 'Hello / World?*' -> Sanitized: '{sanitize_filename('Hello / World?*')}.png'")