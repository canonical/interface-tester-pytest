# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest

from .plugin import InterfaceTester
from .interface_test import interface_test_case


@pytest.fixture(scope="function")
def interface_tester():
    yield InterfaceTester()
