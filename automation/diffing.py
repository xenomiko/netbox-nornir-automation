from pathlib import Path
import logging
import yaml

logger = logging.getLogger(__name__)


def normalize_config(config_text: str) -> list[str]:
    if not config_text:
        return []
    return [line.rstrip() for line in config_text.splitlines() if line.strip()]


def diff_section(
    intended_config: str,
    running_config: str,
) -> dict[str, list[str]]:
    intended_lines = set(normalize_config(intended_config))
    running_lines = set(normalize_config(running_config))
    missing = list(intended_lines - running_lines)
    unmanaged = list(running_lines - intended_lines)
    return {
        "missing": missing,
        "unmanaged": unmanaged,
    }


def load_exceptions(file_path: str) -> dict[str, set[str]]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"yaml file not found at {path.resolve()}")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML file '{path.name}': {e}") from e
    if not data:
        return {}
    if not isinstance(data, dict):
        raise TypeError(
            f"Invalid format in '{path}': expected top-level mapping "
            f"(dict), got {type(data).__name__}"
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
                        f"Exception line in section '{section}' must be "
                        f"a string, got {type(line).__name__}"
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
                f"Section '{section}' must contain a list of lines "
                f"or a string, got {type(lines).__name__}"
            )
    return exceptions


def filter_unmanaged(
    unmanaged_lines: list[str],
    exceptions: dict[str, set[str]],
    section: str,
) -> list[str]:
    if not unmanaged_lines:
        return []
    exempted_lines = exceptions.get(section, set())
    return [line for line in unmanaged_lines if line not in exempted_lines]
