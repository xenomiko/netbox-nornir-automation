from nornir.core.task import Task, Result
from jinja2 import Environment, FileSystemLoader
from builders import build_device_config


def render_config(task: Task, nb) -> Result:
    env = Environment(
        loader=FileSystemLoader("templates"),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    device_config = build_device_config(nb, task)

    platform = task.host.platform
    platform_dir = PLATFORM_TEMPLATE_DIR.get(platform, platform)

    template = env.get_template(f"{platform_dir}/base.j2")
    rendered = template.render(device=device_config)

    return Result(host=task.host, result=rendered)


PLATFORM_TEMPLATE_DIR = {
    "eos": "arista",
    "ios": "cisco",
    "aoscx": "aruba",
}
