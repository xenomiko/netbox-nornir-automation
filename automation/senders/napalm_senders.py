from nornir_napalm.plugins.tasks import napalm_configure
from nornir.core.task import Task, Result


def push_vlan_config(task: Task, config_text: str, dry_run: bool = True) -> Result:
    result = task.run(
        task=napalm_configure,
        configuration=config_text,
        replace=False,
        dry_run=dry_run,
    )
    return result
