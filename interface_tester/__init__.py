# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest

from .pytest_interface_tester import InterfaceTester


@pytest.fixture(scope="function")
def interface_tester():
    yield InterfaceTester()
