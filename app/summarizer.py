from app.kubernetes_client import (
    get_first_container_name,
    get_pod_context,
    get_pod_events,
    get_previous_container_logs,
)
from app.llm import generate_incident_analysis_safely
from app.models import AlertManagerWebhook
from app.prometheus_client import get_restart_increase_context

"""
Currently no LLM yet. "Fake AI" for testing.
Using async because prometheus_client uses `httpx.AsyncClient`
"""
async def summarize_alert(payload: AlertManagerWebhook) -> str:
    final_sections: list[str] = [
        "🚨 Incident Summary",
        "",
        f"Status: {payload.status.upper()}",
        f"Receiver: {payload.receiver}",
        f"Alert count: {len(payload.alerts)}",
    ]

    for index, alert in enumerate(payload.alerts, start=1):
        labels = alert.labels
        annotations = alert.annotations

        alert_name = labels.get("alertname", "UnknownAlert")
        severity = labels.get("severity", "unknown")
        # namespace = labels.get("namespace", "unknown")
        namespace = labels.get("affected_namespace") or labels.get("namespace") or "unknown"
        pod_name = labels.get("pod", "unknown")
        summary = annotations.get("summary", "No summary provided")
        description = annotations.get("description", "No description provided")

        evidence_sections: list[str] = [
            f"Alert #{index}: {alert_name}",
            f"Status: {alert.status.upper()}",
            f"Severity: {severity}",
            f"Namespace: {namespace}",
            f"Pod: {pod_name}",
            f"Summary: {summary}",
            f"Description: {description}",
        ]

        # Actual kubernetes pod state
        if pod_name != "unknown" and namespace != "unknown":
            pod_context = get_pod_context(namespace=namespace, pod_name=pod_name)
            evidence_sections.append(pod_context)

            pod_events = get_pod_events(namespace=namespace, pod_name=pod_name, limit=5)
            evidence_sections.append(pod_events)

            # Add previous log so we find out what happened before the container crashed
            container_name = get_first_container_name(namespace=namespace, pod_name=pod_name)
            previous_logs = get_previous_container_logs(
                namespace=namespace,
                pod_name=pod_name,
                container_name=container_name,
                tail_lines=30
            )
            evidence_sections.append(previous_logs)

            # Add prometheus context so we know why the alert fires
            prometheus_context = await get_restart_increase_context(
                namespace=namespace,
                pod_name=pod_name
            )
            evidence_sections.append(prometheus_context)

        raw_context = "\n\n".join(evidence_sections)

        ai_analysis = await generate_incident_analysis_safely(
            raw_context=raw_context
        )
        final_sections.extend(
            [
                "",
                f"━━━━━━━━ Alert #{index} ━━━━━━━━",
                "",
                f"🤖 AI Analysis for {alert_name}",
                "",
                ai_analysis,
                "",
                "📋 Collected Evidence",
                "",
                raw_context,
                "",
                "🔧 Suggested Manual Checks",
                f"- kubectl describe pod {pod_name} -n {namespace}",
                (
                    f"- kubectl logs {pod_name} "
                    f"-n {namespace} --previous"
                ),
                (
                    f"- kubectl get events -n {namespace} "
                    "--sort-by=.lastTimestamp"
                ),
            ]
        )

    return "\n".join(final_sections)
