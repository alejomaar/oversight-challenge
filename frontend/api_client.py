"""Thin HTTP client for the AWS-hosted Knowledge Base API.

No retrieval, embedding, or generation logic lives here or anywhere in this
app — every function is a passthrough to the API. The Lambda behind it owns
all RAG behavior.
"""

import os

import httpx
import streamlit as st

from constants import DEFAULT_API_BASE_URL


def _config(key: str, default: str = "") -> str:
    if key in os.environ:
        return os.environ[key]
    try:
        return st.secrets[key]
    except Exception:
        return default


API_BASE_URL = _config("API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
API_TOKEN = _config("API_TOKEN", "")


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"
    return headers


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

    if response.status_code in (401, 403):
        return False, response.status_code, "Unauthorized — check API_TOKEN."

    if not response.is_success:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        return False, response.status_code, detail

    try:
        return True, response.status_code, response.json()
    except ValueError:
        return True, response.status_code, {}


def api_get(path: str):
    return api_request("GET", path)


def api_post(path: str, json: dict):
    return api_request("POST", path, json=json)


def api_delete(path: str):
    return api_request("DELETE", path)
