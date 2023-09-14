# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from ops import CharmBase
from scenario.state import State

from interface_tester import InterfaceTester
from interface_tester.collector import gather_test_spec_for_version
from tests.unit.utils import CRI_LIKE_PATH


class CRILikePathTester(InterfaceTester):
    def _collect_interface_test_specs(self):
        gather_test_spec_for_version(
            CRI_LIKE_PATH,
            interface_name=self._interface_name,
            version=self._interface_version,
        )


class DummiCharm(CharmBase):
    pass


@pytest.fixture
def interface_tester(interface_tester: CRILikePathTester):
    interface_tester.configure(
        charm_type=DummiCharm,
        meta={
            "name": "dummi",
            "provides": {"tracing": {"interface": "tracing"}},
            "requires": {"tracing": {"interface": "tracing"}},
        },
        state_template=State(leader=True),
    )
    yield interface_tester
