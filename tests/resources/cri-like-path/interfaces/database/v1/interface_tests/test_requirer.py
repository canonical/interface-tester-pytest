# Copyright 2023 Canonical
# See LICENSE file for licensing details.

from scenario import Relation, State

from interface_tester.interface_test import Tester


def test_no_data_on_created():
    t = Tester(State())
    t.run(event="database-relation-created")
    t.assert_relation_data_empty()


def test_no_data_on_joined():
    t = Tester()
    t.run(event="database-relation-joined")
    t.assert_relation_data_empty()


def test_data_on_changed():
    t = Tester(
        State(
            relations=[
                Relation(
                    endpoint="database",
                    interface="database",
                    remote_app_name="remote",
                    local_app_data={},
                )
            ]
        )
    )
    t.run("database-relation-changed")
    t.assert_relation_data_empty()
