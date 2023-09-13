from pydantic import BaseModel

from interface_tester.schema_base import DataBagSchema


class DBRequirerData(BaseModel):
    foo: str
    bar: int


class RequirerSchema(DataBagSchema):
    """Requirer schema for Tracing."""

    app: DBRequirerData
