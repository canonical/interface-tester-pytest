# Copyright 2023 Canonical
# See LICENSE file for licensing details.

from scenario import State, Relation

from interface_tester.interface_test import Tester


def test_no_data_on_created():
    t = Tester(State())
    state_out = t.run(event='tracing-relation-created')
    t.assert_relation_data_empty()


def test_no_data_on_joined():
    t = Tester()
    state_out = t.run(event='tracing-relation-joined')
    t.assert_relation_data_empty()


def test_data_on_changed():
    t = Tester(State(
        relations=[Relation(
            endpoint='tracing',
            interface='tracing',
            remote_app_name='remote',
            local_app_data={}
        )]
    ))
    state_out = t.run("tracing-relation-changed")
