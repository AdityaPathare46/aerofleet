"""
Pytest configuration and shared fixtures for Space Mission Architect tests.
"""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock
from typing import Dict, Any

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "ERROR"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
# VR pairing sessions work in-process in tests, but must not open LAN sockets (gateway/beacon).
os.environ["AEROFLEET_VR_NETWORK"] = "off"


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_data_dir(project_root) -> Path:
    """Get the test data directory."""
    return project_root / "tests" / "fixtures"


@pytest.fixture
def sample_mission_spec() -> Dict[str, Any]:
    """Provide a sample mission specification for testing."""
    return {
        "overview": {
            "name": "Test Mission to Mars",
            "type": "Single Satellite",
            "priority": "High",
            "duration_value": 2,
            "duration_unit": "Years",
            "objectives": {
                "primary": "Test trajectory planning",
                "secondary": "Validate physics calculations"
            }
        },
        "configuration": {
            "physical": {
                "mass_dry": 1000.0,
                "mass_wet": 2000.0,
                "dimensions": "3x3x3m"
            },
            "propulsion": {
                "type": "Chemical",
                "isp": 320.0,
                "thrust_max": 500.0
            },
            "power": {
                "source": "Solar",
                "generation_w": 2000.0,
                "panel_area": 10.0,
                "efficiency": 0.3
            }
        },
        "orbit": {
            "initial": {
                "a": 6700.0,
                "e": 0.001,
                "i": 28.5
            },
            "target": {
                "type": "Interplanetary",
                "body": "MARS"
            }
        },
        "constraints": {
            "budget": 500.0,
            "launch_window": {
                "start": "2026-01-01",
                "end": "2026-12-31"
            }
        }
    }


@pytest.fixture
def mock_ollama_response():
    """Mock Ollama API response."""
    mock = MagicMock()
    mock.return_value = {
        "message": {
            "content": '{"action": "CONTINUE", "reason": "Mission parameters nominal"}'
        }
    }
    return mock


@pytest.fixture
def mock_spice_data():
    """Mock SPICE kernel data."""
    return {
        "EARTH": [1.496e8, 0, 0],  # km from Sun
        "MARS": [2.279e8, 0, 0],
        "JUPITER": [7.785e8, 0, 0]
    }


@pytest.fixture
def mock_trajectory_engine(mock_spice_data):
    """Mock trajectory engine for testing."""
    from unittest.mock import Mock
    
    engine = Mock()
    engine.plan_mission.return_value = {
        "departure_velocity_vector": [3.0, 0.5, 0.1],
        "arrival_velocity_vector": [2.5, 0.3, 0.05],
        "estimated_delta_v_km_s": 5.7,
        "launch_date": "2026-07-01",
        "arrival_date": "2027-02-15",
        "status": "PHYSICS_VALIDATED"
    }
    engine.get_realistic_delta_v.return_value = 5.7
    
    return engine


@pytest.fixture
def mock_agent():
    """Mock AI agent for testing."""
    from unittest.mock import Mock
    
    agent = Mock()
    agent.reason.return_value = "Mission parameters look acceptable. Recommend proceeding."
    agent.interpret_mission.return_value = {
        "mission_type": "ORBITAL_TRANSFER",
        "origin": "EARTH",
        "target": "MARS",
        "constraints": {
            "max_duration_days": 730,
            "fuel_limit_kg": 1000
        }
    }
    
    return agent


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    from aerofleet.utils.config import Config
    
    config = Config()
    config.environment = "test"
    config.debug = True
    config.llm.ollama_host = "http://localhost:11434"
    config.database.database_url = "sqlite:///:memory:"
    
    return config


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests. Also snapshots/restores
    os.environ: get_config() calls load_dotenv(), which — the first time
    any test boots the real app (e.g. via the api_client fixture) — writes
    this repo's .env values (OLLAMA_HOST, etc.) into os.environ as a
    process-wide side effect that would otherwise silently leak into every
    later test in the same pytest run."""
    import aerofleet.utils.config as config_module
    config_module._config = None

    from aerofleet.safety import policy_store
    policy_store.invalidate_policy_cache()

    env_snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(env_snapshot)


@pytest.fixture
def temp_mission_file(tmp_path):
    """Create a temporary mission file for testing."""
    mission_file = tmp_path / "test_mission.json"
    mission_data = {
        "name": "Test Mission",
        "launch_date": "2026-01-01",
        "target": "MARS"
    }
    
    import json
    with open(mission_file, 'w') as f:
        json.dump(mission_data, f)
    
    return mission_file


# ─────────────────────────────────────────────────────────────────────────
#  AeroFleet drone-dispatch domain fixtures (additive — the fixtures above
#  are legacy holdovers from the original orbital-mechanics project and
#  still serve tests/integration/test_v2_pipeline.py; these are new).
# ─────────────────────────────────────────────────────────────────────────

os.environ.setdefault("USE_MOCK_AGENTS", "true")


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """The slowapi Limiter's storage is a per-process singleton
    (aerofleet/api/rate_limit.py), so without this, whichever test happens
    to be the 6th in a pytest run to hit /auth/login would get a spurious
    429 from a PREVIOUS test's login calls, not its own."""
    from aerofleet.api.rate_limit import limiter

    limiter.reset()
    yield


@pytest.fixture
def api_client():
    """FastAPI TestClient against the real app, used as a context manager
    so startup/shutdown lifecycle events actually fire (init_db, hardware
    telemetry poll loop)."""
    from fastapi.testclient import TestClient
    from aerofleet.api.app import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def fresh_fleet_state():
    """Clears the process-wide FleetState cache before and after a test, so
    drone/order mutations from one test never leak into another. Needed
    because aerofleet.fleet.state._fleet_states is a module-level singleton
    dict, not something the app resets per-request."""
    from aerofleet.fleet import flight_progress
    from aerofleet.fleet import state as fleet_state_module

    fleet_state_module._fleet_states.clear()
    flight_progress.clear()
    yield
    fleet_state_module._fleet_states.clear()
    flight_progress.clear()


@pytest.fixture
def auth_headers(api_client):
    """Registers a throwaway user and returns a ready-to-use Authorization
    header dict."""
    import uuid

    username = f"testuser_{uuid.uuid4().hex[:8]}"
    api_client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "TestPass123!"},
    )
    resp = api_client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "TestPass123!"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_headers(api_client):
    """Registers a throwaway user and flips is_operator=True directly via
    the DB — a real admin endpoint exists now (aerofleet/api/routes/admin.py,
    Phase AI), but tests still go straight to the DB here to avoid coupling
    every operator-gated test's setup to a second, unrelated admin flow; the
    admin endpoint itself has its own dedicated tests
    (tests/integration/test_admin_api.py). Returns a ready-to-use
    Authorization header dict for operator-gated endpoints (hardware
    control, policy proposal approve/reject)."""
    import uuid

    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import User

    username = f"operator_{uuid.uuid4().hex[:8]}"
    api_client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "TestPass123!"},
    )
    with get_db_session() as db:
        user = db.query(User).filter(User.username == username).first()
        user.is_operator = True

    resp = api_client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "TestPass123!"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(api_client):
    """Registers a throwaway user, flips is_admin=True directly via the DB
    (this is the fixture's job specifically so admin-panel tests don't
    depend on the admin panel to create their own first admin — that's
    exactly the bootstrapping problem AEROFLEET_BOOTSTRAP_ADMIN_USERNAME
    solves in real deployments, tested separately). Returns
    (headers, user_id)."""
    import uuid

    from aerofleet.data.database import get_db_session
    from aerofleet.data.models.models import User

    username = f"admin_{uuid.uuid4().hex[:8]}"
    api_client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "TestPass123!"},
    )
    with get_db_session() as db:
        user = db.query(User).filter(User.username == username).first()
        user.is_admin = True
        user_id = user.id

    resp = api_client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "TestPass123!"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user_id


# Skip markers for conditional tests
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "requires_ollama: mark test as requiring Ollama server"
    )
    config.addinivalue_line(
        "markers", "requires_spice: mark test as requiring SPICE kernels"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle skips."""
    # Check if Ollama is available
    try:
        import ollama
        ollama_available = True
    except:
        ollama_available = False
    
    # Check if SPICE kernels are available
    spice_path = Path(__file__).parent.parent / "datasets" / "orbital" / "SPICE"
    spice_available = spice_path.exists()
    
    skip_ollama = pytest.mark.skip(reason="Ollama server not available")
    skip_spice = pytest.mark.skip(reason="SPICE kernels not available")
    
    for item in items:
        if "requires_ollama" in item.keywords and not ollama_available:
            item.add_marker(skip_ollama)
        if "requires_spice" in item.keywords and not spice_available:
            item.add_marker(skip_spice)
