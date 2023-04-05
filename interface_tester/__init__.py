# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest

from .interface_test import interface_test_case
from .plugin import InterfaceTester


@pytest.fixture(scope="function")
def interface_tester():
    yield InterfaceTester()
