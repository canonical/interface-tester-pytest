from pathlib import Path
from textwrap import dedent

import pytest

from interface_tester.collector import (
    collect_tests,
    get_schema_from_module,
    load_schema_module,
)
from interface_tester.interface_test import _has_pydantic_v1


def test_load_schema_module(tmp_path):
    pth = Path(tmp_path) / "foo.py"
    pth.write_text(
        dedent(
            """
FOO: int = 1
        """
        )
    )

    module = load_schema_module(pth)
    assert module.FOO == 1


def test_collect_schemas(tmp_path):
    # unique filename else it will load the wrong module
    root = Path(tmp_path)
    intf = root / "interfaces"
    version = intf / "mytestinterface" / "v0"
    version.mkdir(parents=True)
    (version / "schema.py").write_text(
        dedent(
            """from interface_tester.schema_base import DataBagSchema
                
class RequirerSchema(DataBagSchema):
    foo: int = 1"""
        )
    )

    tests = collect_tests(root)
    assert tests["mytestinterface"]["v0"]["requirer"]["schema"]


def test_collect_schemas_multiple(tmp_path):
    # unique filename else it will load the wrong module
    root = Path(tmp_path)
    intf = root / "interfaces"
    version = intf / "mytestinterfacea" / "v0"
    version.mkdir(parents=True)
    (version / "schema.py").write_text(
        dedent(
            """from interface_tester.schema_base import DataBagSchema

class RequirerSchema(DataBagSchema):
    foo: int = 1"""
        )
    )

    version = intf / "mytestinterfaceb" / "v0"
    version.mkdir(parents=True)
    (version / "schema.py").write_text(
        dedent(
            """from interface_tester.schema_base import DataBagSchema

class RequirerSchema(DataBagSchema):
    foo: int = 2"""
        )
    )

    tests = collect_tests(root)
    if _has_pydantic_v1:
        assert tests["mytestinterfacea"]["v0"]["requirer"]["schema"].__fields__["foo"].default == 1
        assert tests["mytestinterfaceb"]["v0"]["requirer"]["schema"].__fields__["foo"].default == 2

    else:
        assert (
            tests["mytestinterfacea"]["v0"]["requirer"]["schema"].model_fields["foo"].default == 1
        )
        assert (
            tests["mytestinterfaceb"]["v0"]["requirer"]["schema"].model_fields["foo"].default == 2
        )


def test_collect_invalid_schemas(tmp_path):
    # unique filename else it will load the wrong module
    root = Path(tmp_path)
    intf = root / "interfaces"
    version = intf / "mytestinterface2" / "v0"
    version.mkdir(parents=True)
    (version / "schema.py").write_text(
        dedent(
            """from interface_tester.schema_base import DataBagSchema
class ProviderSchema(DataBagSchema):
    foo: int = 2"""
        )
    )

    tests = collect_tests(root)
    assert tests["mytestinterface2"]["v0"]["requirer"]["schema"] is None


@pytest.mark.parametrize(
    "schema_source, schema_name",
    (
        (dedent("""Foo2: int=1"""), "Foo2"),
        (dedent("""Bar: str='baz'"""), "Bar"),
        (
            dedent(
                """
        from typing import List
        
        Baz: List[int]=[1,2,3]"""
            ),
            "Baz",
        ),
    ),
)
def test_get_schema_from_module_wrong_type(tmp_path, schema_source, schema_name):
    # unique filename else it will load the wrong module
    pth = Path(tmp_path) / f"bar{schema_name}.py"
    pth.write_text(schema_source)
    module = load_schema_module(pth)

    # fails because it's not a pydantic model
    with pytest.raises(TypeError):
        get_schema_from_module(module, schema_name)


@pytest.mark.parametrize("schema_name", ("foo", "bar", "baz"))
def test_get_schema_from_module_bad_name(tmp_path, schema_name):
    pth = Path(tmp_path) / "bar3.py"
    pth.write_text("dead: str='beef'")
    module = load_schema_module(pth)

    # fails because it's not found in the module
    with pytest.raises(NameError):
        get_schema_from_module(module, schema_name)
