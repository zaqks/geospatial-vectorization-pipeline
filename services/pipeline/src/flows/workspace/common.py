from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field, validator


class WorkspaceParams(BaseModel):
    uuid: str = Field(..., alias="UUID")

    @validator("uuid")
    def validate_uuid(cls, value: str) -> str:
        return str(UUID(value))

    class Config:
        allow_population_by_field_name = True


def workspace_paths(upload_uuid: str) -> tuple[Path, Path, Path]:
    workspace_dir = Path("/tmp") / upload_uuid
    data_dir = workspace_dir / "data"
    input_png = data_dir / "input.png"
    return workspace_dir, data_dir, input_png