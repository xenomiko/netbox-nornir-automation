import logging
from nornir.core.task import Task, Result
from nornir_scrapli.tasks import send_configs
from scrapli.exceptions import ScrapliException

logger = logging.getLogger(__name__)


def _split_config_lines(config_text: str) -> list[str]:

    lines = []
    for raw_line in config_text.splitlines():
        line = raw_line.rstrip()
        if not line or line.rstrip() == "!":
            continue
        lines.append(line)
    return lines


def push_config(
    task: Task,
    section: str,
    config_text: str,
    dry_run: bool = True,
) -> Result:
    if not config_text or not config_text.strip():
        msg = f"No config to push for section '{section}' — empty config_text."
        logger.warning(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=False, result=msg)
    commands = _split_config_lines(config_text)
    if not commands:
        msg = f"Nothing to send for section '{section}' after normalizing config_text."
        logger.warning(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=False, result=msg)
    if dry_run:
        preview = "\n".join(commands)
        logger.info(
            "[%s] Dry run — would push section '%s':\n%s",
            task.host.name,
            section,
            preview,
        )
        return Result(
            host=task.host,
            failed=False,
            result=preview,
            diff=preview,
            changed=False,
        )
    try:
        from ..getters.scrapli_getters import ensure_scrapli_platform
        ensure_scrapli_platform(task)
        result = task.run(
            task=send_configs,
            configs=commands,
        )
    except ScrapliException as e:
        msg = f"Scrapli error pushing section '{section}': {e}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=True, result=msg)
    except Exception as e:
        msg = f"Failed to push section '{section}': {e}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=True, result=msg)
    output = result[0].result
    logger.info(
        "[%s] Pushed section '%s'. Device output:\n%s",
        task.host.name,
        section,
        output,
    )
    return Result(
        host=task.host,
        failed=result[0].failed,
        result=output,
        diff=output,
        changed=not result[0].failed,
    )
