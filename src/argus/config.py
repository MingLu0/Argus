from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class BackendConfig(BaseModel):
    path: str | None = None


class BackendPolicy(BaseModel):
    missing: str = "warn"
    minimum_successful_reviewers: int = 2


class ArgusConfig(BaseModel):
    backend_policy: BackendPolicy = Field(default_factory=BackendPolicy)
    backends: dict[str, BackendConfig] = Field(default_factory=dict)


def load_config(project_root: Path) -> ArgusConfig:
    config_path = project_root / ".argus" / "config.yaml"
    if not config_path.exists():
        return ArgusConfig()
    data = yaml.safe_load(config_path.read_text()) or {}
    return ArgusConfig.model_validate(data)
