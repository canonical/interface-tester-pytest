# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest

from interface_tester.interface_test import Tester  # noqa F401
from interface_tester.plugin import InterfaceTester
from interface_tester.schema_base import DataBagSchema  # noqa: F401


@pytest.fixture(scope="function")
def interface_tester():
    yield InterfaceTester()
