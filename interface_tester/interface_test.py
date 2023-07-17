# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import dataclasses
import inspect
import logging
import operator
import re
import typing
from contextlib import contextmanager
from enum import Enum
from typing import Callable, Literal, Optional, Union, Any, Dict, List

from scenario import Event, State, Context, Relation

from interface_tester.errors import InvalidTestCaseError, SchemaValidationError

RoleLiteral = Literal["requirer", "provider"]

if typing.TYPE_CHECKING:
    InterfaceNameStr = str
    VersionInt = int
    _SchemaConfigLiteral = Literal["default", "skip", "empty"]
    from interface_tester import DataBagSchema

INTF_NAME_AND_VERSION_REGEX = re.compile(r"/interfaces/(\w+)/v(\d+)/")

logger = logging.getLogger(__name__)


class InvalidTestCase(RuntimeError):
    """Raised if a function decorated with interface_test_case is invalid."""


class Role(str, Enum):
    provider = "provider"
    requirer = "requirer"


@dataclasses.dataclass
class _InterfaceTestContext:
    """Data associated with a single interface test case."""

    interface_name: str
    """The name of the interface that this test is about."""
    version: int
    """The version of the interface that this test is about."""
    role: Role

    # fixme
    charm_type: type
    supported_endpoints: dict
    meta: Any
    config: Any
    actions: Any

    """The role (provider|requirer) that this test is about."""
    schema: Optional["DataBagSchema"] = None
    """Databag schema to validate the output relation with."""
    input_state: Optional[State] = None
    """Initial state that this test should be run with."""


def check_test_case_validator_signature(fn: Callable):
    """Verify the signature of a test case validator function.

    Will raise InvalidTestCase if:
    - the number of parameters is not exactly 1
    - the parameter is not positional only or positional/keyword

    Will pop a warning if the one argument is annotated with anything other than scenario.State
    (or no annotation).
    """
    sig = inspect.signature(fn)
    if not len(sig.parameters) == 1:
        raise InvalidTestCase(
            "interface test case validator expects exactly one "
            "positional argument of type State."
        )

    params = list(sig.parameters.values())
    par0 = params[0]
    if par0.kind not in (par0.POSITIONAL_OR_KEYWORD, par0.POSITIONAL_ONLY):
        raise InvalidTestCase(
            "interface test case validator expects the first argument to be positional."
        )

    if par0.annotation not in (par0.empty, State):
        logger.warning(
            "interface test case validator will receive a State as first and "
            "only positional argument."
        )


_TESTER_CTX: Optional[_InterfaceTestContext] = None


@contextmanager
def tester_context(ctx: _InterfaceTestContext):
    global _TESTER_CTX
    _TESTER_CTX = ctx
    yield
    _TESTER_CTX = None
    if not Tester.__instance__:
        raise NoTesterInstanceError('invalid tester_context usage: no Tester instance created')
    Tester.__instance__._finalize()


class InvalidTesterRunError(RuntimeError):
    """Raised if Tester is being used incorrectly."""

class NoTesterInstanceError(InvalidTesterRunError):
    """Raised if no Tester is created within a tester_context scope."""


class NoSchemaError(InvalidTesterRunError):
    """Raised when schemas cannot be validated because there is no schema."""


class Tester:
    __instance__ = None

    def __init__(self, state_in: State=None, name: str = None):
        """Initializer.

        :param state_in: the input state for this scenario test. Will default to the empty State().
        :param name: the name of the test. Will default to the function's identifier.
        """
        # todo: pythonify
        if Tester.__instance__:
            raise RuntimeError("Tester is a singleton.")
        Tester.__instance__ = self

        if not self.ctx:
            raise RuntimeError('Tester can only be initialized inside a tester context.')

        self._state_template = None
        self._state_in = state_in or State()
        self._name = name

        self._state_out = None  # will be State when has_run is true
        self._has_run = False
        self._has_checked_schema = False

    @property
    def ctx(self):
        return _TESTER_CTX

    def run(self, event: Union[str, Event]):
        assert self.ctx, 'tester cannot run: no _TESTER_CTX set'

        state_out = self._run(event)
        self._state_out = state_out
        return state_out

    def assert_schema_valid(self, schema:"DataBagSchema" = None):
        self._has_checked_schema = True
        if not self._has_run:
            raise RuntimeError('call Tester.run() first')

        if schema:
            logger.info("running test with custom schema")
            databag_schema = schema
        else:
            logger.info("running test with built-in schema")
            databag_schema = self.ctx.schema
            if not databag_schema:
                raise NoSchemaError(
                    f"No schemas found for {self.ctx.interface_name}/{self.ctx.version}/{self.ctx.role};"
                    f"call skip_schema_validation() manually.")

        errors = []
        for relation in [r for r in self._state_out.relations if r.interface == self.ctx.interface_name]:
            try:
                databag_schema.validate(
                    {
                        "unit": relation.local_unit_data,
                        "app": relation.local_app_data,
                    }
                )
            except RuntimeError as e:
                errors.append(e.args[0])
        if errors:
            raise SchemaValidationError(errors)

    def _check_has_run(self):
        if not self._has_run:
            raise InvalidTesterRunError('call Tester.run() first')

    def assert_relation_data_empty(self):
        self._check_has_run()
        # todo
        self._has_checked_schema = True

    def skip_schema_validation(self):
        self._check_has_run()
        # todo
        self._has_checked_schema = True

    def _finalize(self):
        if not self._has_run:
            raise InvalidTesterRunError("call .run() before returning")
        if not self._has_checked_schema:
            # todo:
            raise InvalidTesterRunError("call .skip_schema_validation(), or ... before returning")

        # release singleton
        Tester.__instance__ = None


    def _run(self, event: Union[str, Event]):
        logger.debug(f"running {event}")
        self._has_run = True

        # this is the input state as specified by the interface tests writer. It can
        # contain elements that are required for the relation interface test to work,
        # typically relation data pertaining to the  relation interface being tested.
        input_state = self._state_in

        # state_template is state as specified by the charm being tested, which the charm
        # requires to function properly. Consider it part of the mocking. For example:
        # some required config, a "happy" status, network information, OTHER relations.
        # Typically, should NOT touch the relation that this interface test is about
        #  -> so we overwrite and warn on conflict: state_template is the baseline,
        state = (self._state_template or State()).copy()

        relations = self._generate_relations_state(
            state, input_state,
            self.ctx.supported_endpoints,
            self.ctx.role
        )
        # State is frozen; replace
        modified_state = state.replace(relations=relations)

        # the Relation instance this test is about:
        relation = next(filter(lambda r: r.interface == self.ctx.interface_name, relations))
        # test.EVENT might be a string or an Event. Cast to Event.
        evt: Event = self._coerce_event(event, relation)

        logger.info(f"collected test for {self.ctx.interface_name} with {evt.name}")
        return self._run_scenario(evt, modified_state)

    def _run_scenario(self, event: Event, state: State):
        logger.debug(f"running scenario with state={state}, event={event}")

        ctx = Context(self.ctx.charm_type, meta=self.ctx.meta,
                      actions=self.ctx.actions, config=self.ctx.config)
        return ctx.run(event, state)

    def _coerce_event(self, raw_event: Union[str, Event], relation: Relation) -> Event:
        # if the event being tested is a relation event, we need to inject some metadata
        # or scenario.Runtime won't be able to guess what envvars need setting before ops.main
        # takes over
        if isinstance(raw_event, str):
            ep_name, _, evt_kind = raw_event.rpartition("-relation-")
            if ep_name and evt_kind:
                # this is a relation event.
                # we inject the relation metadata
                # todo: if the user passes a relation event that is NOT about the relation
                #  interface that this test is about, at this point we are injecting the wrong
                #  Relation instance.
                #  e.g. if in interfaces/foo one wants to test that if 'bar-relation-joined' is
                #  fired... then one would have to pass an Event instance already with its
                #  own Relation.
                return Event(
                    raw_event,
                    relation=relation.replace(endpoint=ep_name),
                )

            else:
                return Event(raw_event)

        elif isinstance(raw_event, Event):
            if raw_event._is_relation_event and not raw_event.relation:
                raise InvalidTestCaseError(
                    "This test case was passed an Event representing a relation event."
                    "However it does not have a Relation. Please pass it to the Event like so: "
                    "evt = Event('my_relation_changed', relation=Relation(...))"
                )

            return raw_event

        else:
            raise InvalidTestCaseError(
                f"Expected Event or str, not {type(raw_event)}. "
                f"Invalid test case: {self} cannot cast {raw_event} to Event."
            )

    def _generate_relations_state(
            self, state_template: State, input_state: State, supported_endpoints, role: Role
    ) -> List[Relation]:
        """Merge the relations from the input state and the state template into one.

        The charm being tested possibly provided a state_template to define some setup mocking data
        The interface tests also have an input_state. Here we merge them into one relation list to
        be passed to the 'final' State the test will run with.
        """
        interface_name = self.ctx.interface_name

        for rel in state_template.relations:
            if rel.interface == interface_name:
                logger.warning(
                    f"relation with interface name = {interface_name} found in state template. "
                    f"This will be overwritten by the relation spec provided by the relation "
                    f"interface test case."
                )

        def filter_relations(rels: List[Relation], op: Callable):
            return [r for r in rels if op(r.interface, interface_name)]

        # the baseline is: all relations whose interface IS NOT the interface we're testing.
        relations = filter_relations(state_template.relations, op=operator.ne)

        if input_state:
            # if the charm we're testing specified some relations in its input state, we add those
            # whose interface IS the same as the one we're testing. If other relation interfaces
            # were specified, they will be ignored.
            relations.extend(filter_relations(input_state.relations, op=operator.eq))

            if ignored := filter_relations(input_state.relations, op=operator.eq):
                logger.warning(
                    f"irrelevant relations specified in input state for {interface_name}/{role}."
                    f"These will be ignored. details: {ignored}"
                )

        # if we still don't have any relation matching the interface we're testing, we generate
        # one from scratch.
        if not filter_relations(relations, op=operator.eq):
            # if neither the charm nor the interface specified any custom relation spec for
            # the interface we're testing, we will provide one.
            endpoints_for_interface = supported_endpoints[role]

            if len(endpoints_for_interface) < 1:
                raise ValueError(f"no endpoint found for {role}/{interface_name}.")
            elif len(endpoints_for_interface) > 1:
                raise ValueError(
                    f"Multiple endpoints found for {role}/{interface_name}: "
                    f"{endpoints_for_interface}: cannot guess which one it is "
                    f"we're supposed to be testing"
                )
            else:
                endpoint = endpoints_for_interface[0]

            relations.append(
                Relation(
                    interface=interface_name,
                    endpoint=endpoint,
                )
            )
        logger.debug(
            f"{self}: merged {input_state} and {state_template} --> relations={relations}"
        )
        return relations
