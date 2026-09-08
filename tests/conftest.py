# This is a pytest fixture configuration file that sets up a SiLA server
# and client for testing purposes.
# s. conftest documentation: https://docs.pytest.org/en/latest/fixture.html

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--num-instances",
        action="store",
        default=1,
        help="Number of instances to create test",
    )


@pytest.fixture(scope="session")
def num_instances(pytestconfig):
    return int(pytestconfig.getoption("num_instances"))
