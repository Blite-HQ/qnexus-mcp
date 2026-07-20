import pytest


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

    def list_jobs(self, project=None, status=None):
        return [{"id": "j1", "status": "COMPLETED"}]

    def job_status(self, job_id):
        return {"id": job_id, "status": "COMPLETED"}

    def job_cost(self, job_id):
        return {"id": job_id, "hqc_cost": 0.0}

    def get_results(self, job_id):
        return {"id": job_id, "counts": {"00": 51, "11": 49}}


@pytest.fixture
def fake_client():
    return FakeClient()
