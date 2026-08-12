import logging
from nornir.core.task import Task, Result
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pynetbox import RequestError
from .builders import build_device_config
from .diffing import normalize_config
import difflib

logger = logging.getLogger(__name__)

PLATFORM_TEMPLATE_DIR = {
    "eos": "arista",
    "ios": "cisco",
    "aoscx": "aruba",
}

JINJA_ENV = Environment(
    loader=FileSystemLoader("templates"),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_config(task: Task, nb) -> Result:
    platform = task.host.platform
    platform_dir = PLATFORM_TEMPLATE_DIR.get(platform)
    if platform_dir is None:
        msg = f"Unsupported or missing platform: {platform!r}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=True, result=msg)

    try:
        device_config = build_device_config(nb, task)
    except RequestError as e:
        msg = f"NetBox lookup failed while building config: {e}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=True, result=msg)

    try:
        template = JINJA_ENV.get_template(f"{platform_dir}/base.j2")
        rendered = template.render(device=device_config)
    except TemplateNotFound as e:
        msg = f"Template not found: {e}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=True, result=msg)

    logger.info(f"[{task.host.name}] Rendered config successfully.")
    return Result(host=task.host, result=rendered)


def diff_text(running: str, intended: str) -> list[str]:
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
