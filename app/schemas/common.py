from pydantic import BaseModel, Field


class ImageBox(BaseModel):
    ymin: int = Field(..., ge=0, description="Top coordinate in pixels.")
    xmin: int = Field(..., ge=0, description="Left coordinate in pixels.")
    ymax: int = Field(..., ge=0, description="Bottom coordinate in pixels.")
    xmax: int = Field(..., ge=0, description="Right coordinate in pixels.")


class ApiMessage(BaseModel):
    message: str = Field(..., description="Simple API message.")


class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="Health status of the service.")
    timestamp: str = Field(..., description="UTC timestamp in ISO 8601 format.")


class ServiceInfoResponse(BaseModel):
    name: str = Field(..., description="Service name.")
    status: str = Field(..., description="Current service readiness status.")
    version: str = Field(..., description="Backend application version.")
    docs_url: str = Field(..., description="Swagger UI path.")
    redoc_url: str = Field(..., description="ReDoc documentation path.")
    openapi_url: str = Field(..., description="OpenAPI schema path.")
