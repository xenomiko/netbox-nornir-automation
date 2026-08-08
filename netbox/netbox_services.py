import yaml
from pathlib import Path
import pynetbox
import os
import logging
from pynetbox import RequestError
from typing import Any, Dict
from pynetbox.core.endpoint import Endpoint
from typing import Union, List, Type
from pydantic import BaseModel, ValidationError
import csv

logger = logging.getLogger(__name__)


def get_netbox_client(validate_connection: bool = True) -> pynetbox.core.api.Api:
    NETBOX_TOKEN = os.getenv("NB_TOKEN")
    NETBOX_URL = os.getenv("NB_URL")
    if not NETBOX_TOKEN or not NETBOX_URL:
        error_msg = (
            "Missing required environment variables: NETBOX_URL and/or" " NETBOX_TOKEN"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    nb = pynetbox.api(url=NETBOX_URL, token=NETBOX_TOKEN)
    if validate_connection:
        try:
            nb.status()
        except RequestError as e:
            error_msg = (
                f"Failed to connect or authenticate with NetBox at {NETBOX_URL}: {e}"
            )
            logger.error(error_msg)
            raise ConnectionError(error_msg) from e
    return nb


def load_device_data(file_path: Union[str, Path]):
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"yaml file not found at {path.resolve()}")
    ext = path.suffix.lower()
    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            if ext in (".yaml", ".yml"):
                data = yaml.safe_load(file)
                return data if data is not None else {}
            elif ext == ".csv":
                reader = csv.DictReader(file)
                return list(reader)
            else:
                raise ValueError(
                    f"Unsupported extension '{ext}'. Use .yaml, .yml, or .csv"
                )
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML file '{path.name}': {e}") from e
    except csv.Error as e:
        raise ValueError(f"Error parsing CSV file '{path.name}': {e}") from e


def resolve_object_id(endpoint: Endpoint, **kwargs) -> int:
    obj = endpoint.get(**kwargs)
    if obj is None:
        raise ValueError(
            f"Could not find object in '{endpoint.name}' matching criteria: {kwargs}"
        )
    return obj.id


def sync_object(endpoint: Endpoint, existing_obj, payload: BaseModel):
    payload_dict = payload.model_dump(exclude_none=True)
    try:
        if existing_obj:
            updated = existing_obj.update(payload_dict)
            if updated:
                logger.info(f"[{endpoint.name}] Updated object ID {existing_obj.id}.")
            else:
                logger.info(
                    f"[{endpoint.name}] Object ID {existing_obj.id} is already up-to-date."
                )
            return existing_obj
        created_obj = endpoint.create(payload_dict)
        logger.info(
            f"[{endpoint.name}] Successfully created object ID {created_obj.id}."
        )
        return created_obj
    except RequestError as e:
        logger.error(f"[{endpoint.name}] NetBox API request failed. Error: {e}")
        raise


def sync_resources(
    endpoint: Endpoint,
    items: List[Dict[str, Any]],
    model_class: Type[BaseModel],
    lookup_field: Union[str, List[Union[str, tuple]]] = "slug",
):
    fields = [lookup_field] if isinstance(lookup_field, str) else lookup_field

    def make_key_from_payload(payload: BaseModel) -> tuple:
        key_parts = []
        for f in fields:
            attr_name, _ = f if isinstance(f, tuple) else (f, f)
            key_parts.append(getattr(payload, attr_name))
        return tuple(key_parts)

    def make_key_from_existing(obj) -> tuple:
        key_parts = []
        for f in fields:
            _, param_name = f if isinstance(f, tuple) else (f, f)
            key_parts.append(getattr(obj, param_name, None))
        return tuple(key_parts)

    try:
        existing_objects = list(endpoint.all())
    except RequestError as e:
        logger.error(f"[{endpoint.name}] Failed to fetch existing objects: {e}")
        return []

    existing_by_key = {make_key_from_existing(obj): obj for obj in existing_objects}
    created_or_found_objects = []

    for raw_item in items:
        try:
            validated_payload = model_class.model_validate(raw_item)
        except ValidationError as err:
            logger.error(f"Validation failed for item {raw_item}: {err}")
            continue

        key = make_key_from_payload(validated_payload)
        existing_obj = existing_by_key.get(key)

        try:
            obj = sync_object(endpoint, existing_obj, validated_payload)
            created_or_found_objects.append(obj)

            # Update cache so duplicate items in the same batch target this object
            existing_by_key[key] = obj
        except RequestError as err:
            logger.error(f"Sync failed for item {raw_item}: {err}")
            continue

    return created_or_found_objects


def sync_cable(nb, cables_data: List[Dict[str, Any]]) -> None:
    for cable in cables_data:
        a_side = cable.get("a_side", {})
        b_side = cable.get("b_side", {})
        try:
            dev_a_id = resolve_object_id(nb.dcim.devices, name=a_side.get("device"))
            iface_a = nb.dcim.interfaces.get(
                device_id=dev_a_id, name=a_side.get("interface")
            )
            dev_b_id = resolve_object_id(nb.dcim.devices, name=b_side.get("device"))
            iface_b = nb.dcim.interfaces.get(
                device_id=dev_b_id, name=b_side.get("interface")
            )
        except Exception as err:
            logger.error(f"Error resolving endpoints for cable {cable}: {err}")
            continue
        if not iface_a or not iface_b:
            logger.error(f"interface not found for entry: {cable}")
            continue
        if iface_a.cable or iface_b.cable:
            logger.info(
                f"Cable between {a_side.get('device')}:{a_side.get('interface')} "
                f"and {b_side.get('device')}:{b_side.get('interface')} already exists. Skipping."
            )
            continue
        cable_payload = {
            "status": cable.get("status", "connected"),
            "a_terminations": [
                {"object_type": "dcim.interface", "object_id": iface_a.id}
            ],
            "b_terminations": [
                {"object_type": "dcim.interface", "object_id": iface_b.id}
            ],
        }
        try:
            new_cable = nb.dcim.cables.create(cable_payload)
            logger.info(f"Successfully created cable ID {new_cable.id}")
        except RequestError as err:
            logger.error(f"Failed to create cable for {cable}: {err}")
