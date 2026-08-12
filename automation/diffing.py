def normalize_config(config_text: str) -> str:
    if not config_text:
        return ""
    unified_text = config_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = unified_text.split("\n")
    normalized_lines = [line.rstrip() for line in lines if line.strip()]
    return "\n".join(normalized_lines)


def diff_vlans(intended: dict[int, str], running: dict[int, str]) -> dict:
    to_add = {}
    for vid, name in intended.items():
        if vid not in running:
            to_add[vid] = name
    to_remove = {}
    for vid, name in running.items():
        if vid not in intended:
            to_remove[vid] = name
    to_update = {}
    for vid, name in intended.items():
        if vid in running and running[vid] != name:
            to_update[vid] = name

    return {"add": to_add, "remove": to_remove, "update": to_update}


def reshape_running_vlans(napalm_vlans: dict) -> dict[int, str]:
    running = {}
    for vid_str, data in napalm_vlans.items():
        vid = int(vid_str)
        if vid == 1:
            continue
        running[vid] = data["name"]
    return running
