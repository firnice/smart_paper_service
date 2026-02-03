from pydantic import BaseModel, Field


class ImageBox(BaseModel):
    ymin: int = Field(..., ge=0)
    xmin: int = Field(..., ge=0)
    ymax: int = Field(..., ge=0)
    xmax: int = Field(..., ge=0)


class ApiMessage(BaseModel):
    message: str
