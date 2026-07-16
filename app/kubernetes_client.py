from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


def load_kubernetes_config() -> None:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()  # For testing locally


def get_pod_context(namespace: str, pod_name: str) -> str:
    load_kubernetes_config()

    v1 = client.CoreV1Api()

    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
    except ApiException as exc:
        return f"Unable to fetch pod context: {exc.reason}"

    lines = []

    lines.append("Kubernetes Context:")
    lines.append(f"- Pod: {pod.metadata.name}")
    lines.append(f"- Namespace: {pod.metadata.namespace}")
    lines.append(f"- Phase: {pod.status.phase}")

    if pod.status.container_statuses:
        for container_status in pod.status.container_statuses:
            lines.append(f"- Container: {container_status.name}")
            lines.append(f"  - Ready: {container_status.ready}")
            lines.append(f"  - Restart count: {container_status.restart_count}")

            state = container_status.state

            if state.waiting:
                lines.append(f"    - State: Waiting")
                lines.append(f"    - Reason: {state.waiting.reason}")

            elif state.running:
                lines.append("     - State: Running")

            elif state.terminated:
                lines.append(f"    - State: Terminated")
                lines.append(f"    - Reason: {state.terminated.reason}")
                lines.append(f"    - Exit code: {state.terminated.exit_code}")

    return "\n".join(lines)


def get_pod_events(namespace: str, pod_name: str, limit: int = 5) -> str:
    load_kubernetes_config()

    v1 = client.CoreV1Api()

    try:
        events = v1.list_namespaced_event(
            namespace=namespace,
            field_selector=f"involvedObject.name={pod_name}"
        )
    except ApiException as exc:
        return f"Unable to fetch pods events: {exc.reason}"

    sorted_events = sorted(
        events.items,
        key=lambda event: (
                event.last_timestamp
                or event.event_time
                or event.metadata.creation_timestamp
        ),
        reverse=True
    )

    if not sorted_events:
        return "Recent Events:\n- No recent events found."

    lines = ["Recent Events:"]

    for event in sorted_events[:limit]:
        reason = event.reason or "UnknownReason"
        message = event.message or "No message"
        event_type = event.type or "UnknownType"

        lines.append(f"- [{event_type}] {reason}: {message}")

    return "\n".join(lines)


# Useful for CrashLoopFeedback as it show logs before the container died
def get_previous_container_logs(
        namespace: str,
        pod_name: str,
        container_name: str | None = None,
        tail_lines: int = 30,
) -> str:

    load_kubernetes_config()

    v1 = client.CoreV1Api()

    try:
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container_name,
            previous=True,
            tail_lines=tail_lines,
        )
    except ApiException as exc:
        return f"Previous Container Logs:\n  - Unable to fetch previous logs: {exc.reason}"

    if not logs.strip():
        return "Previous Container Logs:\n  - No previous logs found."

    return f"Previous Container Logs:\n{logs.strip()}"


# For multi-containers pod.
def get_first_container_name(namespace: str, pod_name: str) -> str | None:
    load_kubernetes_config()

    v1 = client.CoreV1Api()

    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
    except ApiException:
        return None

    if not pod.spec.containers:
        return None

    return pod.spec.containers[0].name
