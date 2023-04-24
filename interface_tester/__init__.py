# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest

from .interface_test import interface_test_case  # noqa: F401
from .plugin import InterfaceTester
from .schema_base import DataBagSchema  # noqa: F401


@pytest.fixture(scope="function")
def interface_tester():
    yield InterfaceTester()
