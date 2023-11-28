# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest

from interface_tester.interface_test import Tester
from interface_tester.plugin import InterfaceTester
from interface_tester.schema_base import DataBagSchema

__all__ = ["Tester", "InterfaceTester", "DataBagSchema"]


@pytest.fixture(scope="function")
def interface_tester():
    yield InterfaceTester()
