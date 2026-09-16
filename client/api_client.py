from __future__ import annotations

import requests


class ApiError(RuntimeError):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class ApiClient:
    def __init__(self, base_url: str, company_token: str = "", timeout: float = 8.0):
        self.base_url = base_url.strip().rstrip("/")
        self.company_token = company_token
        self.employee_token = ""
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "PrintOrderManager-MultiStore/1.0"})

    def _request(self, method: str, path: str, token: str = "", **kwargs) -> dict:
        headers = dict(kwargs.pop("headers", {}))
        auth = token or self.employee_token or self.company_token
        if auth:
            headers["Authorization"] = f"Bearer {auth}"
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ApiError(f"Cannot reach the synchronization server: {exc}") from exc
        try:
            data = response.json()
        except ValueError:
            data = {}
        if not response.ok:
            detail = data.get("detail") if isinstance(data, dict) else None
            raise ApiError(
                str(detail or f"Server returned HTTP {response.status_code}"),
                response.status_code,
            )
        return data

    def health(self) -> dict:
        return self._request("GET", "/api/health", token="")

    def company_login(self, company_code: str, password: str) -> dict:
        data = self._request(
            "POST",
            "/api/auth/company-login",
            token="",
            json={
                "company_code": company_code,
                "password": password,
            },
        )
        self.company_token = data["token"]
        return data

    def bootstrap(self) -> dict:
        return self._request("GET", "/api/bootstrap", token=self.company_token)

    def employee_login(self, employee_id: str, pin: str, location_id: str) -> dict:
        data = self._request(
            "POST",
            "/api/auth/employee-login",
            token=self.company_token,
            json={
                "employee_id": employee_id,
                "pin": pin,
                "location_id": location_id,
            },
        )
        self.employee_token = data["token"]
        return data

    def push(self, operations: list[dict]) -> dict:
        return self._request(
            "POST",
            "/api/sync/push",
            token=self.employee_token,
            json={"operations": operations},
        )

    def pull(self, cursor: int, limit: int = 500) -> dict:
        return self._request(
            "GET",
            "/api/sync/pull",
            token=self.employee_token,
            params={"cursor": cursor, "limit": limit},
        )

    def report(self, location_id: str = "", start_date: str = "", end_date: str = "") -> dict:
        return self._request(
            "GET",
            "/api/reports/summary",
            token=self.employee_token,
            params={
                "location_id": location_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    def list_employees(self) -> list[dict]:
        return self._request("GET", "/api/admin/employees", token=self.employee_token)["employees"]

    def create_employee(self, values: dict) -> dict:
        return self._request(
            "POST", "/api/admin/employees", token=self.employee_token, json=values
        )["employee"]

    def update_employee(self, employee_id: str, values: dict) -> dict:
        return self._request(
            "PATCH",
            f"/api/admin/employees/{employee_id}",
            token=self.employee_token,
            json=values,
        )["employee"]
