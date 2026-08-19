import logging
from nornir_napalm.plugins.tasks import napalm_configure
from nornir.core.task import Task, Result

logger = logging.getLogger(__name__)


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
    try:
        result = task.run(
            task=napalm_configure,
            configuration=config_text,
            replace=False,
            dry_run=dry_run,
        )
    except Exception as e:
        msg = f"NAPALM push failed for section '{section}': {e}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=True, result=msg)
    diff = result[0].diff if result[0].diff else "(no changes)"
    logger.info(
        "[%s] %s section '%s' (dry_run=%s). Diff:\n%s",
        task.host.name,
        "Simulated push of" if dry_run else "Pushed",
        section,
        dry_run,
        diff,
    )
    return Result(
        host=task.host,
        failed=False,
        result=diff,
        diff=diff,
        changed=bool(result[0].diff),
    )
