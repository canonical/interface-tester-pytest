# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
class InterfaceTesterValidationError(ValueError):
    """Raised if the InterfaceTester configuration is incorrect or incomplete."""


class InvalidTestCaseError(RuntimeError):
    """Raised if an interface test case is invalid."""


class InterfaceTestsFailed(RuntimeError):
    """Raised if interface tests completed with errors."""


class NoTestsRun(RuntimeError):
    """Raised if no interface test was collected during a run() call."""


class SchemaValidationError(RuntimeError):
    """Raised when schema validation fails on one or more relations."""
