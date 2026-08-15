import difflib


def normalize_config(config_text: str) -> list[str]:
    if not config_text:
        return []
    normalized_text = [
        line.rstrip() for line in config_text.splitlines() if line.strip()
    ]
    return normalized_text


def diff_texts(running: str, intended: str) -> list[str]:
    running_lines = normalize_config(running).splitlines()
    intended_lines = normalize_config(intended).splitlines()
    diff = list(
        difflib.unified_diff(
            running_lines,
            intended_lines,
            fromfile="running",
            tofile="intended",
            lineterm="",
        )
    )
    return diff
