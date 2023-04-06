from pathlib import Path
from textwrap import dedent

import pytest

from interface_tester.collector import get_schema_from_module, load_schema_module, collect_tests


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
    "schema_source, schema_name, foo_value",
    (
        (
            dedent(
                """from interface_tester.schema_base import DataBagSchema
                
class RequirerSchema(DataBagSchema):
    foo = 1"""
            ),
            "RequirerSchema",
            1,
        ),
        (
            dedent(
                """from interface_tester.schema_base import DataBagSchema
class ProviderSchema(DataBagSchema):
    foo = 2"""
            ),
            "ProviderSchema",
            2,
        ),
        (
            dedent(
                """from interface_tester.schema_base import DataBagSchema
class Foo(DataBagSchema):
    foo = 3"""
            ),
            "Foo",
            3,
        ),
    ),
)
def test_collect_tests(tmp_path, schema_source, schema_name, foo_value):
    # unique filename else it will load the wrong module
    root = Path(tmp_path)
    intf = root / 'interfaces'
    version = intf / f'my{schema_name}' / 'v0'
    version.mkdir(parents=True)
    (version / f"schema.py").write_text(schema_source)

    tests = collect_tests(root)
    assert tests[f"my{schema_name}"]['v0']['requirer']['schema']


@pytest.mark.parametrize(
    "schema_source, schema_name",
    (
        (dedent("""Foo2=1"""), "Foo2"),
        (dedent("""Bar='baz'"""), "Bar"),
        (dedent("""Baz=[1,2,3]"""), "Baz"),
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
    pth.write_text("dead='beef'")
    module = load_schema_module(pth)

    # fails because it's not found in the module
    with pytest.raises(NameError):
        get_schema_from_module(module, schema_name)
