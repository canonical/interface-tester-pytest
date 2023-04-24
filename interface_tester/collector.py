# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
"""
This module contains logic to gather interface tests from the relation interface specifications.
It also contains a `pprint_tests` function to display a pretty-printed listing of the
collected tests. This file is executable and will run that function when invoked.

If you are contributing a relation interface specification or modifying the tests, charms, or
schemas for one, you can execute this file to ascertain that all relevant data is being gathered
correctly.
"""
import dataclasses
import importlib
import json
import logging
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Type, TypedDict

import pydantic
import yaml

from .interface_test import DataBagSchema, Role, get_registered_test_cases

if TYPE_CHECKING:
    from .interface_test import _InterfaceTestCase

logger = logging.getLogger("interface_tests_checker")

_NotFound = object()


class _TestSetup(TypedDict):
    """Charm-specific configuration for the interface tester.

    Contains information to configure the tester."""

    location: Optional[str]
    """Path to a python file, relative to the charm's git repo root, where the `identifier` 
    below can be found. If not provided defaults to "tests/interfaces/conftest.py" """

    identifier: Optional[str]
    """Name of a python identifier pointing to a pytest fixture yielding a 
    configured InterfaceTester instance. If not provided defaults to "interface_tester" """


@dataclasses.dataclass
class _CharmTestConfig:
    name: str
    """The name of the charm."""
    url: str
    """Url of a git repository where the charm source can be found."""
    test_setup: Optional[_TestSetup] = None
    """Interface tester configuration. Can be left empty. All values will be defaulted."""
    branch: Optional[str] = None
    """Name of the git branch where to find the interface tester configuration. 
    If not provided defaults to "main". """

    def __hash__(self):
        return hash((self.name, self.url, self.branch))


class _CharmsDotYamlSpec(TypedDict):
    """Specification of the `charms.yaml` file each interface/version dir should contain."""

    providers: List[_CharmTestConfig]
    requirers: List[_CharmTestConfig]


class _RoleTestSpec(TypedDict):
    """The tests, schema, and charms for a single role of a given relation interface version."""

    tests: List["_InterfaceTestCase"]
    schema: Optional[Type[DataBagSchema]]
    charms: List[_CharmTestConfig]


class InterfaceTestSpec(TypedDict):
    """The tests, schema, and charms for both roles of a given relation interface version."""

    provider: _RoleTestSpec
    requirer: _RoleTestSpec


def get_schema_from_module(module: object, name: str) -> Type[pydantic.BaseModel]:
    """Tries to get ``name`` from ``module``, expecting to find a pydantic.BaseModel."""
    schema_cls = getattr(module, name, None)
    if not schema_cls:
        raise NameError(name)
    if not issubclass(schema_cls, pydantic.BaseModel):
        raise TypeError(type(schema_cls))
    return schema_cls


def load_schema_module(schema_path: Path) -> types.ModuleType:
    """Import the schema.py file as a python module."""
    # so we can import without tricks
    sys.path.append(str(schema_path.parent))

    # strip .py
    module_name = str(schema_path.with_suffix("").name)

    # if a previous call to load_schema_module has loaded a
    # module with the same name, this will conflict.
    if module_name in sys.modules:
        del sys.modules[module_name]

    # Otherwise we'll get an error when we re-run @validator
    # fixme: is there a better way to do this?
    logger.debug("Clearing pydantic.class_validators._FUNCS")
    pydantic.class_validators._FUNCS.clear()  # noqa

    try:
        module = importlib.import_module(module_name)
    except ImportError:
        raise
    finally:
        # cleanup
        sys.path.remove(str(schema_path.parent))

    return module


def get_schemas(file: Path) -> Dict[Literal["requirer", "provider"], Type[DataBagSchema]]:
    """Load databag schemas from schema.py file."""
    if not file.exists():
        logger.warning(f"File does not exist: {file}")
        return {}

    try:
        module = load_schema_module(file)
    except ImportError as e:
        logger.error(f"Failed to load module {file}: {e}")
        return {}

    out = {}
    for role, name in (("provider", "ProviderSchema"), ("requirer", "RequirerSchema")):
        try:
            out[role] = get_schema_from_module(module, name)
        except NameError:
            logger.warning(
                f"Failed to load {name} from {file}: " f"schema not defined for role: {role}."
            )
        except TypeError as e:
            logger.error(
                f"Found object called {name!r} in {file}; "
                f"expecting a DataBagSchema subclass, not {e.args[0]!r}."
            )
    return out


def _gather_charms_for_version(version_dir: Path) -> Optional[_CharmsDotYamlSpec]:
    """Attempt to read the `charms.yaml` for this version sudir.

    On failure, return None.
    """
    charms_yaml = version_dir / "charms.yaml"
    if not charms_yaml.exists():
        return None

    charms = None
    try:
        charms = yaml.safe_load(charms_yaml.read_text())
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        logger.error(f"failed to decode {charms_yaml}: " f"verify that it is valid: {e}")
    except FileNotFoundError as e:
        logger.error(f"not found: {e}")
    if not charms:
        return None

    providers = charms.get("providers", [])
    requirers = charms.get("requirers", [])

    if not isinstance(providers, list) or not isinstance(requirers, list):
        raise TypeError(
            f"{charms_yaml} file has unexpected providers/requirers spec; "
            f"expected two lists of dicts (yaml mappings); "
            f"got {type(providers)}/{type(requirers)}. "
            f"Invalid charms.yaml format."
        )

    provider_configs = []
    requirer_configs = []
    for source, destination in ((providers, provider_configs), (requirers, requirer_configs)):
        for item in source:
            try:
                cfg = _CharmTestConfig(**item)
            except TypeError:
                logger.error(
                    f"failure parsing {item} to _CharmTestConfig; invalid charm test "
                    f"configuration in {version_dir}/charms.yaml:providers"
                )
                continue
            destination.append(cfg)

    spec: _CharmsDotYamlSpec = {"providers": provider_configs, "requirers": requirer_configs}
    return spec


def _gather_test_cases_for_version(version_dir: Path, interface_name: str, version: int):
    """Collect interface test cases from a directory containing an interface version spec."""

    interface_tests_dir = version_dir / "interface_tests"

    provider_test_cases = []
    requirer_test_cases = []

    if interface_tests_dir.exists():
        # so we can import without tricks
        sys.path.append(str(interface_tests_dir))

        for possible_test_file in interface_tests_dir.glob("*.py"):
            # strip .py
            module_name = str(possible_test_file.with_suffix("").name)
            try:
                _ = importlib.import_module(module_name)
            except ImportError as e:
                logger.error(f"Failed to load module {possible_test_file}: {e}")
                continue

            cases = get_registered_test_cases()
            provider_test_cases.extend(cases[(interface_name, version, Role.provider)])
            requirer_test_cases.extend(cases[(interface_name, version, Role.requirer)])

        if not (requirer_test_cases or provider_test_cases):
            logger.error(f"no valid test case files found in {interface_tests_dir}")

        # remove from import search path
        sys.path.pop(-1)
    return provider_test_cases, requirer_test_cases


def gather_test_spec_for_version(
    version_dir: Path, interface_name: str, version: int
) -> InterfaceTestSpec:
    """Collect interface tests from an interface/version subdirectory.

    Given a directory containing an interface specification (conform the template),
    collect and return the interface tests for this version.
    """

    provider_test_cases, requirer_test_cases = _gather_test_cases_for_version(
        version_dir, interface_name, version
    )
    schemas = get_schemas(version_dir / "schema.py")
    charms = _gather_charms_for_version(version_dir)

    return {
        "provider": {
            "tests": provider_test_cases,
            "schema": schemas.get("provider"),
            "charms": charms.get("providers", []) if charms else [],
        },
        "requirer": {
            "tests": requirer_test_cases,
            "schema": schemas.get("requirer"),
            "charms": charms.get("requirers", []) if charms else [],
        },
    }


def _gather_tests_for_interface(
    interface_dir: Path, interface_name: str
) -> Dict[str, InterfaceTestSpec]:
    """Collect interface tests from an interface subdirectory.

    Given a directory containing an interface specification (conform the template),
    collect and return the interface tests for each available version.
    """
    tests = {}
    for version_dir in interface_dir.glob("v*"):
        try:
            version_n = int(version_dir.name[1:])
        except TypeError:
            logger.error(f"Unable to parse version {version_dir.name} as an integer. Skipping...")
            continue
        tests[version_dir.name] = gather_test_spec_for_version(
            version_dir, interface_name, version_n
        )
    return tests


def collect_tests(path: Path, include: str = "*") -> Dict[str, Dict[str, InterfaceTestSpec]]:
    """Gather the test cases collected from this path.

    Returns a dict structured as follows:
    - interface name (e.g. "ingress"):
      - version name (e.g. "v2"):
        - role (e.g. "requirer"):
          - tests: [list of interface_test._InterfaceTestCase]
          - schema: <pydantic.BaseModel>
          - charms:
            - name: foo
              url: www.github.com/canonical/foo
    """
    logger.info(f"collecting tests from {path}:{include}")
    tests = {}

    for interface_dir in (path / "interfaces").glob(include):
        interface_dir_name = interface_dir.name
        if interface_dir_name.startswith("__"):  # ignore __template__ and python-dirs
            continue  # skip
        logger.info(f"collecting tests for interface {interface_dir_name}")
        interface_name = interface_dir_name.replace("-", "_")
        tests[interface_name] = _gather_tests_for_interface(interface_dir, interface_name)

    return tests
