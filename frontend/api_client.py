"""Thin HTTP client for the AWS-hosted Knowledge Base API.

No retrieval, embedding, or generation logic lives here or anywhere in this
app — every function is a passthrough to the API. The Lambda behind it owns
all RAG behavior.
"""

import os

import httpx

from constants import DEFAULT_API_BASE_URL

API_BASE_URL = os.environ.get("API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
API_TOKEN = os.environ.get("API_TOKEN", "")


def _auth_headers() -> dict:
    headers = {}
    if API_TOKEN:
        headers["x-api-key"] = API_TOKEN
    return headers


def _headers() -> dict:
    return {"Content-Type": "application/json", **_auth_headers()}


def _parse_response(response: httpx.Response):
    """Returns (ok, status_code, data_or_error_message)."""
    if response.status_code in (401, 403):
        return False, response.status_code, "Unauthorized — check API_TOKEN."

    try:
        data = response.json()
    except ValueError:
        return False, response.status_code, response.text or f"API returned a non-JSON response (status {response.status_code})."

    return response.is_success, response.status_code, data


def api_request(method: str, path: str, **kwargs):
    """Returns (ok, status_code, data_or_error_message)."""
    url = f"{API_BASE_URL}{path}"
    try:
        response = httpx.request(method, url, headers=_headers(), timeout=65, **kwargs)
    except httpx.ConnectError:
        return False, None, f"Could not connect to {API_BASE_URL}. Is the API running and reachable?"
    except httpx.TimeoutException:
        return False, None, "Request timed out waiting for the API."
    except httpx.RequestError as e:
        return False, None, str(e)

    return _parse_response(response)


def api_get(path: str):
    return api_request("GET", path)


def api_post(path: str, json: dict):
    return api_request("POST", path, json=json)


def api_delete(path: str):
    return api_request("DELETE", path)


def api_upload_file(path: str, filename: str, content: bytes, content_type: str):
    """Multipart file upload. Returns (ok, status_code, data_or_error_message)."""
    url = f"{API_BASE_URL}{path}"
    try:
        response = httpx.post(
            url,
            headers=_auth_headers(),
            files={"file": (filename, content, content_type)},
            timeout=65,
        )
    except httpx.ConnectError:
        return False, None, f"Could not connect to {API_BASE_URL}. Is the API running and reachable?"
    except httpx.TimeoutException:
        return False, None, "Request timed out waiting for the API."
    except httpx.RequestError as e:
        return False, None, str(e)

    return _parse_response(response)
