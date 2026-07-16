# AI Assisted Kubernetes Incident Summarizer

## Proposition

Kubernetes alerts often lack context for rapid diagnosis. This service automatically collects pod state, recent events, previous container logs, and Promthetheus metrics, then generates a structured incident analysis and send it to Microsoft Teams.<br>


## Architecture and workflow

![](./images/ai_assisted_kubernetes_alert.drawio.png)

1. Pods exposes metrics and the state is saved on etcd, which is part of the control plane component. `prometheus-kube-state-metrics`  in the `monitoring` namespace scrapes these metrics from `etcd`.
2. A pod goes into pending state. A `PrometheusRule` in the `monitoring` namespace is created with an expression `increase(kube_pod_container_status_restarts_total{namespace="business", pod="biz-pod"}[5m]) > 0`.
   3. This expression equates to **true** when `biz-pod` in the `business` namespace restarts more than once in the last 5 minutes.
4. `Prometheus` evaluates `PrometheusRule`. When an expression is **true**, Prometheus will fire an alert to the `AlertManager`, which handles the alert.
   5. The `AlertManager configmap` tells `AlertManager` how to handle the alert. In this case, send the alert to the `ai-incident-summarizer` service.
6. The `ai-incident-summarizer` service receives the alert. It then calls the Ollama API, inserting the alert payload as a parameter.
7. Ollama evaluates the alert, then send the insight back to the `ai-incident-summarizer` service.
8. Lastly, the `ai-incident-summarizer` send the insights to Microsoft Teams.
   9. The Microsoft Teams webhook url is stored as a Kubernetes secret, and referenced by the `ai-incident-summarizer` service.

<br>

****

<br>

## End result and sample output
<br>

![](./images/ai_analysis.png)

**Likely Cause**: Database connection failure leading to container restart.<br>
**Impact**: Application unavailable due to container crashes.<br>
**Evidence**:
* Pod crash-demo is restarting repeatedly (Restart count: 4).
* Reason for restarts: "CrashLoopBackOff" indicating container failure.
* Previous container logs show a "connection refused" error when attempting to connect to the database service `db.ai.svc:5432`.
* Prometheus shows a significant increase in container restarts within the last 5 minutes.<br>

**Recommended Actions**:
1. Investigate the database service db.ai.svc:5432 for connectivity issues (e.g., service availability, firewall rules, DNS resolution).
2. Verify the database connection string and credentials within the container configuration.
3. Check the application logs for more detailed error messages related to the database connection attempt.
4. Consider increasing the application's retry logic or implementing a circuit breaker pattern to handle transient database connection failures.

**Confidence**: High

## Key capabilities

* Receives AlertManager webhooks through FastAPI
* Filters AI-enabled alerts using the `ai-summarizer=true` label.
* Retrieves pod status, restart counts, events and previous logs.
* Queries Prometheus for supporting time-series evidence.
* Generates structured analysis using an Ollama-hosted LLM.
* Sends incident summaries to Microsoft Teams.
* Uses read-only Kubernetes RBAC.
* Continues with partial results when optional dependencies failed.

# Quick Start

```bash
# Clone the repository
git clone <repo>
cd <repo>

# Create a python virtual env and install requirements
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the test cases (optional)
pytest

# Containerize the ai-incident-summarizer application
docker build -t ai-incident-summarizer:<tag>
# Load the image into minikube so the pod will be able to pull the image
minikube load image ai-incident-summarizer:<tag> --daemon

# Apply kubernetes manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/rbac/rbac.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/alertmanagerconfig.yaml
```

<br>

# Limitations and Roadmap

## Current limitations

* Only resource of type `Pod` is supported at the moment.
* In a multi-container pod, only the first container is selected.
* Processes alerts synchronously.
* No webhook authentication yet.
* Ollama endpoint is assumed to be trusted.
* Microsoft Teams is the only notification target.
* No resolved message at the moment.

## Future plans and improvements

* Instead of using generic secrets, we can use sealed-secrets.
* The Kubernetes component, including kube-prometheus-stack, can be managed using FluxCD.

# Demo

## 1. Create a pod which crashes

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: crash-demo
  namespace: ai
  labels:
    app: crash-demo
spec:
  containers:
    - name: crash-demo
      image: busybox:1.36
      command:
        - sh
        - -c
        - |
          echo "Starting crash demo application"
          echo "Connecting to database..."
          echo "ERROR: failed to connect to database at db.ai.svc:5432"
          echo "Reason: connection refused"
          sleep 5
          exit 1
  restartPolicy: Always
```

## 2. Create a PrometheusRule for this crash demo

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: ai-summarizer-crash-demo-alert
  namespace: monitoring
  labels:
    release: prometheus
spec:
  groups:
    - name: ai-summarizer-crash-demo.rules
      rules:
        - alert: AISummarizerPodCrashLooping
          expr: increase(kube_pod_container_status_restarts_total{namespace="ai", pod="crash-demo"}[5m]) > 0
          for: 30s
          labels:
            severity: warning
            ai_summarizer: "true"
            namespace: monitoring  # For current AertmanagerConfig routing
            affected_namespace: ai  # Tells our summarizer the actual affected workload is in the ai namespace
            pod: crash-demo
          annotations:
            summary: "Pod crash-demo is restarting repeatedly"
            description: "Pod crash-demo in namespace ai has restarted in the last 5 minutes."
```

## 3. Check if alert is firing

```bash
kubectl port-forward service/prometheus-kube-prometheus-prometheus -n monitoring 9090
```

![](./images/alert_firing.png)

## 4. Check if you receive the alert workflow card on Teams.

![](./images/ai_analysis.png)