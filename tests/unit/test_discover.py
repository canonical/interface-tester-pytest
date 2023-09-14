from utils import CRI_LIKE_PATH

from interface_tester.cli.discover import pprint_tests


def test_discover(capsys):
    pprint_tests(CRI_LIKE_PATH, "*")
    out = capsys.readouterr().out
    assert (
        out.strip()
        == f"""
collecting tests for * from root = {CRI_LIKE_PATH}
Discovered:
database:
  - v1:
   - provider:
      - test_data_on_changed
      - test_no_data_on_created
      - test_no_data_on_joined
     - schema NOT OK
     - charms:
       - foo-k8s (https://github.com/canonical/foo-k8s-operator) custom_test_setup=no
   - requirer:
      - test_data_on_changed
      - test_no_data_on_created
      - test_no_data_on_joined
     - schema OK
     - <no charms>

tracing:
  - v42:
   - provider:
      - test_data_on_changed
      - test_no_data_on_created
      - test_no_data_on_joined
     - schema NOT OK
     - charms:
       - tempo-k8s (https://github.com/canonical/tempo-k8s-operator) custom_test_setup=no
   - requirer:
      - test_data_on_changed
      - test_no_data_on_created
      - test_no_data_on_joined
     - schema OK
     - <no charms>
""".strip()
    )
