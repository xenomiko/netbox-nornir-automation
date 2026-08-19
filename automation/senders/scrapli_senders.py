import logging
from nornir.core.task import Task, Result
from nornir.core.exceptions import NornirSubTaskError
from nornir_scrapli.tasks import send_configs
from scrapli.exceptions import ScrapliException

logger = logging.getLogger(__name__)


def _split_config_lines(config_text: str) -> list[str]:
    lines = []
    for raw_line in config_text.splitlines():
        line = raw_line.strip()
        if not line or line == "!":
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
        result = task.run(
            task=send_configs,
            configs=commands,
            stop_on_failed=False,
        )
    except NornirSubTaskError as e:
        task.host.close_connections()
        sub_result = e.result
        scrapli_output = getattr(sub_result, "result", None)
        scrapli_exc = getattr(sub_result, "exception", None)
        detail = str(scrapli_output) if scrapli_output else str(scrapli_exc)
        msg = f"Failed to push section '{section}': {detail}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=True, result=msg)
    except ScrapliException as e:
        task.host.close_connections()
        msg = f"Scrapli error pushing section '{section}': {e}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=True, result=msg)
    except Exception as e:
        task.host.close_connections()
        msg = f"Failed to push section '{section}': {type(e).__name__}: {e}"
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
