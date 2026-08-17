import difflib
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)


def normalize_config(config_text: str) -> list[str]:
    if not config_text:
        return []
    normalized_text = [
        line.rstrip() for line in config_text.splitlines() if line.strip()
    ]
    return normalized_text


def diff_texts(running: str, intended: str) -> list[str]:
    running_lines = normalize_config(running)
    intended_lines = normalize_config(intended)
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


def diff_section(intended_config: str, running_config: str) -> dict[str, list[str]]:
    intended_lines = normalize_config(intended_config)
    running_lines = normalize_config(running_config)
    diff = difflib.ndiff(intended_lines, running_lines)
    missing = []
    unmanaged = []
    for line in diff:
        if line.startswith("- "):
            missing.append(line[2:])
        elif line.startswith("+ "):
            unmanaged.append(line[2:])
    return {"missing": missing, "unmanaged": unmanaged}


def load_exceptions(file_path: str) -> dict[str, set[str]]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"yaml file not found at {path.resolve()}")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            return {}
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML file '{path.name}': {e}") from e
    if not isinstance(data, dict):
        raise TypeError(
            f"Invalid format in '{path}': expected top-level mapping (dict), "
            f"got {type(data).__name__}"
        )
    exceptions: dict[str, set[str]] = {}
    for section, lines in data.items():
        if lines is None:
            exceptions[section] = set()
        elif isinstance(lines, list):
            normalized_lines = set()
            for line in lines:
                if not isinstance(line, str):
                    raise TypeError(
                        f"Exception line in section '{section}' must be a string, "
                        f"got {type(line).__name__}"
                    )
                normalized = normalize_config(line)
                if normalized:
                    normalized_lines.add(normalized[0])
            exceptions[section] = normalized_lines
        elif isinstance(lines, str):
            normalized = normalize_config(lines)
            exceptions[section] = set(normalized)
        else:
            raise TypeError(
                f"Section '{section}' must contain a list of lines or a string, "
                f"got {type(lines).__name__}"
            )
    return exceptions
