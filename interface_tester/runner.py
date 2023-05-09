import typing
from typing import Dict, List, Optional, Type

from ops.charm import CharmBase
from scenario import Event, Relation, State, trigger

from .errors import InvalidTestCaseError
from .interface_test import SchemaConfig, logger
from .schema_base import DataBagSchema

if typing.TYPE_CHECKING:
    from .interface_test import _InterfaceTestCase


def _assert_case_plays(
    event: Event, state: State, charm_type: Type["CharmBase"], meta, actions, config
) -> State:
    try:
        state_out = trigger(
            state,
            event,
            charm_type=charm_type,
            meta=meta,
            actions=actions,
            config=config,
        )
    except Exception as e:
        msg = (
            f"Failed check 1: scenario errored out: ({type(e).__name__}){e}. Could not play scene."
        )
        raise RuntimeError(msg) from e
    return state_out


def _assert_state_out_valid(state_out: State, test: "_InterfaceTestCase"):
    """Run the test's validator against the output state.

    Raise RuntimeError if any exception is raised by the validator.
    """
    try:
        test.run(state_out)
    except Exception as e:
        msg = f"Failed check 2: validating scene output: {e}"
        raise RuntimeError(msg) from e


def _assert_schema_valid(schema: DataBagSchema, relation: Relation) -> None:
    """Validate the relation databags against this schema.

    Raise RuntimeError if any exception is raised by the validator.
    """
    try:
        schema.validate(
            {
                "unit": relation.local_unit_data,
                "app": relation.local_app_data,
            }
        )
    except Exception as e:
        msg = f"Failed check 3: validating schema on scene output: {e}"
        logger.error(msg)
        raise RuntimeError(msg) from e


def _assert_schemas_valid(
    test: "_InterfaceTestCase", state_out: State, schema: DataBagSchema, interface_name: str
) -> List[str]:
    """Check that all relations using the interface comply with the provided schema."""
    test_schema = test.schema
    if test_schema is SchemaConfig.skip:
        logger.info("Schema validation skipped as per interface_test_case schema config.")
        return []

    if test_schema == SchemaConfig.default:
        schema = schema
    elif test_schema == SchemaConfig.empty:
        schema = DataBagSchema()
    elif isinstance(test_schema, DataBagSchema):
        schema = test_schema
    else:
        raise InvalidTestCaseError(
            "interface_test_case schema should be either a SchemaConfig instance or a "
            f"DataBagSchema instance, not {type(test_schema)}."
        )

    errors = []
    for relation in [r for r in state_out.relations if r.interface == interface_name]:
        try:
            _assert_schema_valid(schema=schema, relation=relation)
        except RuntimeError as e:
            errors.append(e.args[0])
    return errors


def run_test_case(
    test: "_InterfaceTestCase",
    schema: Optional["DataBagSchema"],
    event: Event,
    state: State,
    interface_name: str,
    # the charm type we're testing
    charm_type: Type["CharmBase"],
    # charm metadata yamls
    meta: Dict,
    config: Dict,
    actions: Dict,
) -> List[str]:
    """Run an interface test case.

    This will run three checks in sequence:
    - play the scenario (check that the charm runs without exceptions) and
      obtain the output state
    - validate the output state (by calling the test-case-provided validator with
      the output state as argument)
    - validate the schema against the relations in the output state.

    It will return a list of strings, representing any issues encountered in any of the checks.
    """
    errors: List[str] = []
    logger.info(f"running test {test.name!r}")
    logger.info("check 1/3: scenario play")
    try:
        state_out = _assert_case_plays(
            event=event,
            state=state,
            charm_type=charm_type,
            meta=meta,
            config=config,
            actions=actions,
        )
    except RuntimeError as e:
        errors.append(e.args[0])
        logger.error("scenario couldn't run: aborting test.", exc_info=True)
        return errors

    logger.info("check 2/3: scenario output state validation")
    # todo: consistency check? or should we rely on scenario's?
    try:
        _assert_state_out_valid(state_out=state_out, test=test)
    except RuntimeError as e:
        errors.append(e.args[0])

    logger.info("check 3/3: databag schema validation")
    if not schema:
        logger.info("schema validation step skipped: no schema provided")
        return errors
    errors.extend(
        _assert_schemas_valid(
            test=test, state_out=state_out, schema=schema, interface_name=interface_name
        )
    )
    return errors
