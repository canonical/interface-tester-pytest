import pytest
from utils import CRI_LIKE_PATH

from interface_tester.collector import collect_tests
from interface_tester.interface_test import (
    InvalidTestCase,
    check_test_case_validator_signature,
)


def test_signature_checker_too_many_params():
    def _foo(a, b, c):
        pass

    with pytest.raises(InvalidTestCase):
        check_test_case_validator_signature(_foo)


def test_signature_checker_bad_type_annotation(caplog):
    def _foo(a: int):
        pass

    check_test_case_validator_signature(_foo)
    assert (
        "interface test case validator will receive a State as first and "
        "only positional argument." in caplog.text
    )


def test_signature_checker_too_many_opt_params():
    def _foo(a, b=2, c="a"):
        pass

    with pytest.raises(InvalidTestCase):
        check_test_case_validator_signature(_foo)


def test_load_from_mock_cri():
    tests = collect_tests(CRI_LIKE_PATH)
    provider = tests["tracing"]["v42"]["provider"]
    assert len(provider["tests"]) == 3
    assert not provider["schema"]
    assert provider["charms"][0].name == "tempo-k8s"

    requirer = tests["tracing"]["v42"]["requirer"]
    assert len(requirer["tests"]) == 3
    assert requirer["schema"]
    assert not requirer["charms"]
