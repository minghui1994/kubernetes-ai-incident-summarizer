import os
from urllib.parse import quote

import httpx


class PrometheusNotConfiguredError(Exception):
    pass


def get_prometheus_base_url() -> str:
    prometheus_base_url = os.getenv("PROMETHEUS_BASE_URL")

    if not prometheus_base_url:
        raise PrometheusNotConfiguredError(
            "PROMETHEUS_BASE_URL environment variable is not configured."
        )

    return prometheus_base_url.rstrip("/")


async def query_prometheus(query: str) -> dict:
    prometheus_base_url = get_prometheus_base_url()
    url = f"{prometheus_base_url}/api/v1/query"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url, params={"query": query})
        response.raise_for_status()
        return response.json()


def build_restart_increase_query(namespace: str, pod_name: str) -> str:
    return (
        'increase(kube_pod_container_status_restarts_total'
        f'{{namespace="{namespace}", pod="{pod_name}"}}[5m])'
    )


async def get_restart_increase_context(namespace: str, pod_name: str) -> str:
    query = build_restart_increase_query(namespace=namespace, pod_name=pod_name)

    try:
        result = await(query_prometheus(query))
    except PrometheusNotConfiguredError:
        return "Prometheus Context:\n- Skipped: PROMETHEUS_BASE_URL is not configured"
    except httpx.HTTPError as exc:
        return f"Prometheus Context:\n- Unabled to query Prometheus: {exc}"

    data = result.get("data", {})
    result_items = data.get("result", [])

    if not result_items:
        return (
            "Prometheus Context:\n"
            "- Restart increase in last 5m: no data\n"
            f"- Query: {query}"
        )

    lines = ["Prometheus Context:"]

    for item in result_items:
        metric = item.get("metric", {})
        value = item.get("value", [])

        container = metric.get("container", "unknown")
        restart_value = value[1] if len(value) > 1 else "unknown"

        lines.append(f"- Container: {container}")
        lines.append(f"  - Restart increase in last 5m: {restart_value}")

    lines.append(f"- Query: {query}")

    return "\n".join(lines)
