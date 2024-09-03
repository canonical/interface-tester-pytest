import tempfile
from pathlib import Path
from textwrap import dedent

import pytest
from ops import CharmBase
from scenario import State
from utils import CRI_LIKE_PATH

from interface_tester import InterfaceTester
from interface_tester.collector import gather_test_spec_for_version
from interface_tester.errors import InvalidTestCaseError, SchemaValidationError
from interface_tester.interface_test import (
    InvalidTesterRunError,
    NoSchemaError,
    NoTesterInstanceError,
    Tester,
)


class LocalTester(InterfaceTester):
    _RAISE_IMMEDIATELY = True

    def _collect_interface_test_specs(self):
        return gather_test_spec_for_version(
            CRI_LIKE_PATH / "interfaces" / self._interface_name / f"v{self._interface_version}",
            interface_name=self._interface_name,
            version=self._interface_version,
        )


class DummiCharm(CharmBase):
    pass


@pytest.fixture
def interface_tester():
    interface_tester = LocalTester()
    interface_tester.configure(
        charm_type=DummiCharm,
        meta={
            "name": "dummi",
            # interface tests should be agnostic to endpoint names
            "provides": {"dead": {"interface": "tracing"}},
            "requires": {"beef-req": {"interface": "tracing"}},
        },
        state_template=State(leader=True),
    )
    yield interface_tester


def test_local_run(interface_tester):
    interface_tester.configure(
        interface_name="tracing",
        interface_version=42,
    )
    interface_tester.run()


def _setup_with_test_file(test_file: str, schema_file: str = None):
    td = tempfile.TemporaryDirectory()
    temppath = Path(td.name)

    class TempDirTester(InterfaceTester):
        _RAISE_IMMEDIATELY = True

        def _collect_interface_test_specs(self):
            pth = temppath / "interfaces" / self._interface_name / f"v{self._interface_version}"

            test_dir = pth / "interface_tests"
            test_dir.mkdir(parents=True)
            test_provider = test_dir / "test_provider.py"
            test_provider.write_text(test_file)

            if schema_file:
                schema_path = pth / "schema.py"
                schema_path.write_text(schema_file)

            return gather_test_spec_for_version(
                pth,
                interface_name=self._interface_name,
                version=self._interface_version,
            )

    interface_tester = TempDirTester()
    interface_tester.configure(
        interface_name="tracing",
        charm_type=DummiCharm,
        meta={
            "name": "dummi",
            # interface tests should be agnostic to endpoint names
            "provides": {"dead": {"interface": "tracing"}},
            "requires": {"beef-req": {"interface": "tracing"}},
        },
        state_template=State(leader=True),
    )

    return interface_tester


def test_error_if_skip_schema_before_run():
    tester = _setup_with_test_file(
        dedent(
            """
from scenario import State, Relation

from interface_tester.interface_test import Tester

def test_data_on_changed():
    t = Tester(State(
        relations={Relation(
            endpoint='foobadooble',  # should not matter
            interface='tracing',
            remote_app_name='remote',
            local_app_data={}
        )}
    ))
    t.skip_schema_validation()
"""
        )
    )

    with pytest.raises(InvalidTesterRunError):
        tester.run()


def test_error_if_not_relation_event():
    tester = _setup_with_test_file(
        dedent(
            """
from scenario import State, Relation

from interface_tester.interface_test import Tester

def test_data_on_changed():
    t = Tester(State(
        relations={Relation(
            endpoint='foobadooble',  # should not matter
            interface='tracing',
            remote_app_name='remote',
            local_app_data={}
        )}
    ))
    t.run("foobadooble-changed")
    t.skip_schema_validation()
"""
        )
    )

    with pytest.raises(InvalidTestCaseError) as e:
        tester.run()

    assert e.match(
        "Bad interface test specification: event foobadooble-changed is not a relation event."
    )


def test_error_if_assert_relation_data_empty_before_run():
    tester = _setup_with_test_file(
        dedent(
            """
from scenario import State, Relation

from interface_tester.interface_test import Tester

def test_data_on_changed():
    t = Tester(State(
        relations={Relation(
            endpoint='foobadooble',  # should not matter
            interface='tracing',
            remote_app_name='remote',
            local_app_data={}
        )}
    ))
    t.assert_relation_data_empty()
"""
        )
    )

    with pytest.raises(InvalidTesterRunError):
        tester.run()
    assert not Tester.__instance__


def test_error_if_assert_schema_valid_before_run():
    tester = _setup_with_test_file(
        dedent(
            """
from scenario import State, Relation

from interface_tester.interface_test import Tester

def test_data_on_changed():
    t = Tester(State(
        relations={Relation(
            endpoint='foobadooble',  # should not matter
            interface='tracing',
            remote_app_name='remote',
            local_app_data={}
        )}
    ))
    t.assert_schema_valid()
"""
        )
    )

    with pytest.raises(InvalidTesterRunError):
        tester.run()


def test_error_if_assert_schema_without_schema():
    tester = _setup_with_test_file(
        dedent(
            """
from scenario import State, Relation

from interface_tester.interface_test import Tester

def test_data_on_changed():
    t = Tester(State(
        relations={Relation(
            endpoint='foobadooble',  # should not matter
            interface='tracing',
            remote_app_name='remote',
            local_app_data={}
        )}
    ))
    state_out = t.run("axolotl-relation-changed")
    t.assert_schema_valid()
"""
        )
    )

    with pytest.raises(NoSchemaError):
        tester.run()


def test_error_if_return_before_schema_call():
    tester = _setup_with_test_file(
        dedent(
            """
from scenario import State, Relation

from interface_tester.interface_test import Tester

def test_data_on_changed():
    t = Tester(State(
        relations={Relation(
            endpoint='foobadooble',  # should not matter
            interface='tracing',
            remote_app_name='remote',
            local_app_data={}
        )}
    ))
    state_out = t.run("axolotl-relation-changed")
"""
        )
    )

    with pytest.raises(InvalidTesterRunError):
        tester.run()


def test_error_if_return_without_run():
    tester = _setup_with_test_file(
        dedent(
            """
from scenario import State, Relation

from interface_tester.interface_test import Tester

def test_data_on_changed():
    t = Tester(State(
        relations={Relation(
            endpoint='foobadooble',  # should not matter
            interface='tracing',
            remote_app_name='remote',
            local_app_data={}
        )}
    ))
    
"""
        )
    )

    with pytest.raises(InvalidTesterRunError):
        tester.run()


def test_error_if_return_without_tester_init():
    tester = _setup_with_test_file(
        dedent(
            """
from scenario import State, Relation

from interface_tester.interface_test import Tester

def test_data_on_changed():
    pass
    
"""
        )
    )

    with pytest.raises(NoTesterInstanceError):
        tester.run()


@pytest.mark.parametrize(
    "endpoint", ("foo-one", "prometheus-scrape", "foobadoodle", "foo-one-two")
)
@pytest.mark.parametrize("evt_type", ("changed", "created", "joined", "departed", "broken"))
def test_valid_run(endpoint, evt_type):
    tester = _setup_with_test_file(
        dedent(
            f"""
 from scenario import State, Relation

 from interface_tester.interface_test import Tester
 from interface_tester.schema_base import DataBagSchema

 def test_data_on_changed():
     t = Tester(State(
         relations={{Relation(
             endpoint='{endpoint}',  # should not matter
             interface='tracing',
             remote_app_name='remote',
             local_app_data={{}}
         )}}
     ))
     state_out = t.run("{endpoint}-relation-{evt_type}")
     t.assert_schema_valid(schema=DataBagSchema())
 """
        )
    )

    tester.run()


def test_valid_run_default_schema():
    tester = _setup_with_test_file(
        dedent(
            """
 from scenario import State, Relation

 from interface_tester.interface_test import Tester
 from interface_tester.schema_base import DataBagSchema

 def test_data_on_changed():
     t = Tester(State(
         relations={Relation(
             endpoint='foobadooble',  # should not matter
             interface='tracing',
             remote_app_name='remote',
             local_app_data={"foo":"1"},
             local_unit_data={"bar": "smackbeef"}
         )}
     ))
     state_out = t.run("axolotl-relation-changed")
     t.assert_schema_valid()
 """
        ),
        schema_file=dedent(
            """
from interface_tester.interface_test import Tester
from interface_tester.schema_base import DataBagSchema, BaseModel
 
class Foo(BaseModel):
    foo:int=1 
class Bar(BaseModel):
    bar:str
    
class ProviderSchema(DataBagSchema):
    unit: Bar
    app: Foo
"""
        ),
    )

    tester.run()


def test_default_schema_validation_failure():
    tester = _setup_with_test_file(
        dedent(
            """
 from scenario import State, Relation

 from interface_tester.interface_test import Tester
 from interface_tester.schema_base import DataBagSchema

 def test_data_on_changed():
     t = Tester(State(
         relations={Relation(
             endpoint='foobadooble',  # should not matter
             interface='tracing',
             remote_app_name='remote',
             local_app_data={"foo":"abc"},
             local_unit_data={"bar": "smackbeef"}
         )}
     ))
     state_out = t.run("axolotl-relation-changed")
     t.assert_schema_valid()
 """
        ),
        schema_file=dedent(
            """
    from interface_tester.interface_test import Tester
    from interface_tester.schema_base import DataBagSchema, BaseModel

    class Foo(BaseModel):
        foo:int=1 
    class Bar(BaseModel):
        bar:str

    class ProviderSchema(DataBagSchema):
        unit: Bar
        app: Foo
    """
        ),
    )

    with pytest.raises(SchemaValidationError):
        tester.run()


def test_valid_run_custom_schema():
    tester = _setup_with_test_file(
        dedent(
            """
 from scenario import State, Relation

 from interface_tester.interface_test import Tester
 from interface_tester.schema_base import DataBagSchema, BaseModel
 
 class Foo(BaseModel):
    foo:int=1 
 class Bar(BaseModel):
    bar:str
    
 class FooBarSchema(DataBagSchema):
     unit: Bar
     app: Foo
     
 def test_data_on_changed():
     t = Tester(State(
         relations={Relation(
             endpoint='foobadooble',  # should not matter
             interface='tracing',
             remote_app_name='remote',
             local_app_data={"foo":"1"},
             local_unit_data={"bar": "smackbeef"}
         )}
     ))
     state_out = t.run("axolotl-relation-changed")
     t.assert_schema_valid(schema=FooBarSchema)
 """
        )
    )

    tester.run()


def test_invalid_custom_schema():
    tester = _setup_with_test_file(
        dedent(
            """
 from scenario import State, Relation

 from interface_tester.interface_test import Tester
 from interface_tester.schema_base import DataBagSchema, BaseModel

 class Foo(BaseModel):
    foo:int=1 
 class Bar(BaseModel):
    bar:str

 class FooBarSchema(DataBagSchema):
     unit: Bar
     app: Foo

 def test_data_on_changed():
     t = Tester(State(
         relations={Relation(
             endpoint='foobadooble',  # should not matter
             interface='tracing',
             remote_app_name='remote',
             local_app_data={"foo":"abc"},
             local_unit_data={"bar": "smackbeef"}
         )}
     ))
     state_out = t.run("axolotl-relation-changed")
     t.assert_schema_valid(schema=FooBarSchema)
 """
        )
    )
    with pytest.raises(SchemaValidationError):
        tester.run()
