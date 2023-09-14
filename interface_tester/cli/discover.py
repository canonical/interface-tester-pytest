from pathlib import Path
from typing import Callable

import typer

from interface_tester.collector import _CharmTestConfig, collect_tests


def pprint_tests(
    path: Path = typer.Argument(
        Path(), help="Path to the root of a charm-relation-interfaces-compliant repository root."
    ),
    include: str = typer.Option("*", help="String for globbing interface names."),
):
    """Pretty-print a listing of the interface tests specified in charm-relation-interfaces."""
    return _pprint_tests(path, include)


def _pprint_tests(path: Path = Path(), include="*"):
    """Pretty-print a listing of the interface tests specified in this repository."""
    print(f"collecting tests for {include} from root = {path.absolute()}")
    tests = collect_tests(path=path, include=include)
    print("Discovered:")

    def pprint_case(case: Callable):
        print(f"      - {case.__name__}")

    # sorted by interface first, version then
    for interface, versions in sorted(tests.items()):
        if not versions:
            print(f"{interface}: <no tests>")
            print()
            continue

        print(f"{interface}:")

        for version, roles in sorted(versions.items()):
            print(f"  - {version}:")

            by_role = {role: roles[role] for role in {"requirer", "provider"}}

            for role, test_spec in sorted(by_role.items()):
                print(f"   - {role}:")

                tests = test_spec["tests"]
                schema = test_spec["schema"]

                for test_cls in sorted(tests, key=lambda fn: fn.__name__):
                    pprint_case(test_cls)

                if not tests:
                    print("     - <no tests>")

                if schema:
                    # todo: check if unit/app are given.
                    print("     - schema OK")
                else:
                    print("     - schema NOT OK")

                charms = test_spec["charms"]
                if charms:
                    print("     - charms:")
                    charm: _CharmTestConfig
                    for charm in sorted(charms, key=lambda cfg: cfg.name):
                        if isinstance(charm, str):
                            print("       - <BADLY FORMATTED>")
                            continue

                        custom_test_setup = "yes" if charm.test_setup else "no"
                        print(
                            f'       - {charm.name} ({charm.url or "NO URL"}) '
                            f"custom_test_setup={custom_test_setup}"
                        )

                else:
                    print("     - <no charms>")

        print()


if __name__ == "__main__":
    _pprint_tests(Path())
