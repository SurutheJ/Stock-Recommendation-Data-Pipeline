import pytest

from fdp.acquisition.fixture_client import FixtureClient
from fdp.modeling.database import get_engine, get_session_factory, init_db


@pytest.fixture()
def session_factory():
    engine = get_engine("sqlite://")
    init_db(engine)
    return get_session_factory(engine)


@pytest.fixture()
def fixture_client():
    return FixtureClient()
