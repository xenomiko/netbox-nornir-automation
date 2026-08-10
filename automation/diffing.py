def normalize_config(config_text: str) -> str:
    if not config_text:
        return ""
    unified_text = config_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = unified_text.split("\n")
    normalized_lines = [line.rstrip() for line in lines if line.strip()]
    return "\n".join(normalized_lines)
