from pathlib import Path
from textwrap import dedent

import pytest

from interface_tester.collector import (
    get_schema_from_module,
    load_schema_module,
)


def test_load_schema_module(tmp_path):
    pth = Path(tmp_path) / "foo.py"
    pth.write_text(
        dedent(
            """
FOO = 1
        """
        )
    )

    module = load_schema_module(pth)
    assert module.FOO == 1


@pytest.mark.parametrize(
    "module_contents, schema_name, foo_value",
    (
        (
            dedent(
                """import pydantic
class RequirerSchema(pydantic.BaseModel):
    foo = 1"""
            ),
            "RequirerSchema",
            1,
        ),
        (
            dedent(
                """import pydantic
class ProviderSchema(pydantic.BaseModel):
    foo = 2"""
            ),
            "ProviderSchema",
            2,
        ),
        (
            dedent(
                """import pydantic
class Foo(pydantic.BaseModel):
    foo = 3"""
            ),
            "Foo",
            3,
        ),
    ),
)
def test_get_schema_from_module(tmp_path, module_contents, schema_name, foo_value):
    # unique filename else it will load the wrong module
    pth = Path(tmp_path) / f"bar{schema_name}.py"
    pth.write_text(module_contents)
    module = load_schema_module(pth)

    requirer_schema = get_schema_from_module(module, schema_name)
    assert requirer_schema.__fields__["foo"].default == foo_value


@pytest.mark.parametrize(
    "module_contents, schema_name",
    (
        (dedent("""Foo2=1"""), "Foo2"),
        (dedent("""Bar='baz'"""), "Bar"),
        (dedent("""Baz=[1,2,3]"""), "Baz"),
    ),
)
def test_get_schema_from_module_wrong_type(tmp_path, module_contents, schema_name):
    # unique filename else it will load the wrong module
    pth = Path(tmp_path) / f"bar{schema_name}.py"
    pth.write_text(module_contents)
    module = load_schema_module(pth)

    # fails because it's not a pydantic model
    with pytest.raises(TypeError):
        get_schema_from_module(module, schema_name)


@pytest.mark.parametrize("schema_name", ("foo", "bar", "baz"))
def test_get_schema_from_module_bad_name(tmp_path, schema_name):
    pth = Path(tmp_path) / "bar3.py"
    pth.write_text("dead='beef'")
    module = load_schema_module(pth)

    # fails because it's not found in the module
    with pytest.raises(NameError):
        get_schema_from_module(module, schema_name)
