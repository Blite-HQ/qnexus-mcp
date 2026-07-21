import types

import pytest

from qnexus_mcp.config import ServerConfig
from qnexus_mcp.context import bind_state


class FakeClient:
    """In-memory stand-in for the Nexus client, so tools/guards are testable offline."""

    def __init__(self, logged_in: bool = True) -> None:
        self._logged_in = logged_in

    def auth_status(self):
        return {
            "logged_in": self._logged_in,
            "hint": None if self._logged_in else "run: qnx login",
        }

    def whoami(self):
        return {"user": "tester@example.com"}

    def list_devices(self):
        return [{"name": "H2-1LE", "status": "online", "billable": False}]

    def list_projects(self):
        return [{"id": "p1", "name": "demo"}]

    def get_quota(self):
        return [{"name": "simulation", "used": 0, "limit": 100}]

    def list_jobs(self):
        return [{"id": "j1", "status": "COMPLETED"}]

    def job_status(self, job_id):
        return {"id": job_id, "status": "COMPLETED"}

    def job_cost(self, job_id):
        return {"id": job_id, "hqc_cost": 0.0}

    def get_results(self, job_id):
        return {"id": job_id, "counts": {"00": 51, "11": 49}}

    def estimate_cost(self, circuit, n_shots, device):
        return 0.0 if device.upper().endswith("LE") else 3.0

    def compile(self, circuit, device, project=None):
        return {"device": device, "compiled": "compiled-ok"}

    def submit(self, circuit, n_shots, device, project=None, max_cost=None, idempotency_key=None):
        return {"job_id": "j-new", "device": device, "idempotency_key": idempotency_key}

    def wait_and_results(self, job_id, timeout=None):
        return {"job_id": job_id, "counts": {"00": 51, "11": 49}}

    def create_project(self, name, description=None):
        return {"name": name, "id": "proj-new"}

    def upload_circuit(self, circuit, project, name):
        return {"name": name, "id": "circ-new", "project": project}

    def cancel_job(self, job_id):
        return {"job_id": job_id, "cancelled": True}

    def delete_job(self, job_id):
        return {"job_id": job_id, "deleted": True}

    def archive_project(self, name):
        return {"name": name, "archived": True}

    def delete_project(self, name):
        return {"name": name, "deleted": True}


@pytest.fixture
def fake_client():
    return FakeClient()


@pytest.fixture
def make_ctx():
    """Factory: build a minimal Context-like object carrying bound server state."""

    def _make(client, config=None):
        server = types.SimpleNamespace()
        bind_state(server, client, config or ServerConfig())
        return types.SimpleNamespace(fastmcp=server)

    return _make
