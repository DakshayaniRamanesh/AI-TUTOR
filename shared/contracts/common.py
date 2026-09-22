"""
Common contracts and base models for Kestrel's transport layer.
"""
import math
from enum import Enum
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

CURRENT_SCHEMA_VERSION = "1.0.0"

class ContractModel(BaseModel):
    """
    Base class for all transport contracts.
    """
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=True
    )
    schema_version: str = Field(default=CURRENT_SCHEMA_VERSION)

StableId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

class CoordinateSpace(str, Enum):
    ITEM = "ITEM"
    SCENE = "SCENE"
    VIEW = "VIEW"
    SCREEN = "SCREEN"

class CanvasBBox(ContractModel):
    x: float
    y: float
    width: float = Field(ge=0.0)
    height: float = Field(ge=0.0)
    coordinate_space: CoordinateSpace = Field(default=CoordinateSpace.SCENE)

    @field_validator("x", "y", "width", "height", mode="after")
    @classmethod
    def reject_inf_nan(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Coordinates and dimensions must be finite numbers.")
        return v
