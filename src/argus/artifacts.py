from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import yaml
from pydantic import BaseModel


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "run"


def ensure_run_dirs(run_dir: Path) -> None:
    for relative_path in ["reviews", "logs", "artifacts"]:
        (run_dir / relative_path).mkdir(parents=True, exist_ok=True)


def copy_topic(topic_path: Path, run_dir: Path) -> None:
    shutil.copyfile(topic_path, run_dir / "topic.md")


def write_yaml(path: Path, model: BaseModel | dict) -> None:
    data = model.model_dump(mode="json") if isinstance(model, BaseModel) else model
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def write_json(path: Path, model: BaseModel | dict | list) -> None:
    if isinstance(model, BaseModel):
        data = model.model_dump(mode="json")
    elif isinstance(model, list):
        data = [
            item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in model
        ]
    else:
        data = model
    path.write_text(json.dumps(data, indent=2) + "\n")


def append_event(run_dir: Path, event: dict) -> None:
    with (run_dir / "events.jsonl").open("a") as event_file:
        event_file.write(json.dumps(event, default=str) + "\n")
