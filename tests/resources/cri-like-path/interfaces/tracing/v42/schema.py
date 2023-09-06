from enum import Enum
from typing import List

from pydantic import BaseModel, Json

from interface_tester.schema_base import DataBagSchema


class IngesterProtocol(str, Enum):
    otlp_grpc = "otlp_grpc"
    otlp_http = "otlp_http"
    zipkin = "zipkin"
    tempo = "tempo"


class Ingester(BaseModel):
    port: str
    protocol: IngesterProtocol


class TracingRequirerData(BaseModel):
    host: str
    ingesters: Json[List[Ingester]]


class RequirerSchema(DataBagSchema):
    """Requirer schema for Tracing."""

    app: TracingRequirerData
