# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
class InterfaceTesterValidationError(ValueError):
    """Raised if the InterfaceTester configuration is incorrect or incomplete."""


class InvalidTestCaseError(RuntimeError):
    """Raised if an interface test case is invalid."""
