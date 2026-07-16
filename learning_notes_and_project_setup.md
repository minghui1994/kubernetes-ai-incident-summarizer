# 1. AI alert summarizer application 

## 1.1 Running the Python application locally

Create and activate a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

<br>

Install dependencies:

```bash
pip3 install -r requirements.txt
```

<br>

Run the app:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

* `uvicorn` is the webserver.
  * FastAPI does not listen for HTTP requests by itself. It needs a server.
  * `uvicorn` command means start a web server using Uvicorn.
  * Request flow
    * curl request
    * Uvicorn receives HTTP request
    * Uvicorn passes request to FastAPI
    * FastAPI runs /healthz function
    * Uvicorn sends response back.
* `app.main:app` means
  * From the Python module app.main, find the FastAPI object called `app`.
  * Inside `app/main.py`, we have the line `app = FastAPI()`
* `--reload` is for development, it means to restart the server automatically when code changes.
* `--host 0.0.0.0` means to listen on all available network interface, important for Docker and Kubernetes.
  * Inside a container, if your app only listens on `127.0.0.1` (localhost), it may only be reachable inside the container itself.
  * `0.0.0.0` means to accept traffic from outside the container too.

<br>

Test health endpoint

```bash
curl http://localhost:8000/healthz
# Expected output: {"status": "ok"}
```

<br>

In another terminal, test with

```bash
curl -X POST http://localhost:8000/webhook/alertmanager \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "ai-summarizer",
    "status": "firing",
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "HighPodRestartCount",
          "severity": "warning",
          "namespace": "default",
          "pod": "crash-demo"
        },
        "annotations": {
          "summary": "Pod has restarted",
          "description": "Pod crash-demo in namespace default has restarted."
        },
        "startsAt": "2026-05-13T01:00:00Z"
      }
    ],
    "groupLabels": {
      "alertname": "HighPodRestartCount"
    },
    "commonLabels": {
      "severity": "warning"
    },
    "commonAnnotations": {
      "summary": "Pod has restarted"
    },
    "externalURL": "http://alertmanager.example.com"
  }'
```

<br>

## 1.1. Testing the Python application

From the root directory

```bash
pytest

PYTHONPATH=. pytest  # Run this if Python complains module not found.
```

Alternatively, create a `pytest.ini` in the project root, then add

```ini
[pytest]
pythonpath = .
```

With this, you can simply run `pytest`.

* Running `PYTHONPATH=. pytest` tells Python to also search the current directory when importing modules.
* pytest does a few things
  * Look for test files
  * Imports those test files
  * Find functions starting with `test_`
  * Runs those test functions
  * Reports pass/fail
* By default, pytest looks for files like:
  * test_*.py
  * *_test.py

<br>

****

<br>

# 2. Deploy application onto Kubernetes

## 2.1. Dockerize application

```dockerfile
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```


Build docker image:

```bash
docker build -t ai-incident-summarizer:0.1.0
```

Run container

```bash
docker run --rm -p 8000:8000 ai-incident-summarizer:0.1.0
```

Test in another terminal

```bash
curl http://localhost:8000/healthz

curl -X POST http://localhost:8000/webhook/alertmanager \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "ai-summarizer",
    "status": "firing",
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "HighPodRestartCount",
          "severity": "warning",
          "namespace": "default",
          "pod": "crash-demo"
        },
        "annotations": {
          "summary": "Pod has restarted",
          "description": "Pod crash-demo in namespace default has restarted."
        },
        "startsAt": "2026-05-13T01:00:00Z"
      }
    ]
  }'
```

<br>

****

<br>

## 2.2. Deploy summarizer to minikube

Load image into minikube

```bash
minikube image load ai-incident-summarizer:0.1.0 --daemon

minikube image ls | grep ai-incident-summarizer  # verify
```

<br>

### 2.2.1. Kubernetes manifests

**deployment**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-incident-summarizer
  namespace: ai
  labels:
    app: ai-incident-summarizer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ai-incident-summarizer
  template:
    metadata:
      labels:
        app: ai-incident-summarizer
    spec:
      containers:
        - name: ai-incident-summarizer
          image: ai-incident-summarizer:0.1.0
          imagePullPolicy: Never  # Tells kubernetes not to pull from Docker Hub, use the image already loaded inside Minikube.
          ports:
            - name: http
              containerPort: 8000
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8000
            initialDelaySeconds: 3
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 20
```

* For minikube testing, need to set imagePullPolicy to `Never`.
  * Without this, Kubernetes may try to pull `ai-incident-summarizer:0.1.0` from the internet and fail.

<br>

**Service**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: ai-incident-summarizer
  namespace: ai
  labels:
    app: ai-incident-summarizer
spec:
  type: ClusterIP
  selector:
    app: ai-incident-summarizer
  ports:
    - name: http
      port: 8000
      targetPort: 8000
      
```

* This gives the app an internal cluster DNS name: `ai-incident-summarizer.ai.svc.cluster.local`.
* Later, Alertmanager can send webhooks to `http://ai-incident-summarizer.ai.svc:8000/webhook/alertmanager`

<br>

## 2.3. Test from machine with port-forward

```bash
kubectl port-forward svc/ai-incident-summarizer -n ai 8000:8000
```

In another terminal:

```bash
curl http://localhost:8000/healthz

curl -X POST http://localhost:8000/webhook/alertmanager \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "ai-summarizer",
    "status": "firing",
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "HighPodRestartCount",
          "severity": "warning",
          "namespace": "default",
          "pod": "crash-demo"
        },
        "annotations": {
          "summary": "Pod has restarted",
          "description": "Pod crash-demo in namespace default has restarted."
        },
        "startsAt": "2026-05-13T01:00:00Z"
      }
    ]
  }'
```

## 2.4. Testing it with Teams

1. Start a meeting, then exit.
2. Go to meeting chat, click on the `...`, then select workflows.
3. Choose a template, can start with `Send webhook alerts to a channel` or `Send webhook alerts to a chat`.
4. Save the webhook link.
5. Create a kubernetes secret for the webhook link

```bash
kubectl create secret generic ai-incident-summarizer-secret -n ai \
  --from-literal=TEAMS_WEBHOOK_URL='https://your-teams-webhook-url-here'
```

6. Updated deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-incident-summarizer
  namespace: ai
  labels:
    app: ai-incident-summarizer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ai-incident-summarizer
  template:
    metadata:
      labels:
        app: ai-incident-summarizer
    spec:
      containers:
        - name: ai-incident-summarizer
          image: ai-incident-summarizer:0.2.0
          imagePullPolicy: Never  # Tells kubernetes not to pull from Docker Hub, use the image already loaded inside Minikube.
          ports:
            - name: http
              containerPort: 8000
          env:
            - name: TEAMS_WEBHOOK_URL
              valueFrom:
                secretKeyRef:
                  name: ai-incident-summarizer-secret
                  key: TEAMS_WEBHOOK_URL
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8000
            initialDelaySeconds: 3
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 20
```

7. Apply the deployment and verify

```bash
kubectl exec deployment/ai-incident-summarizer -n ai -- printenv | grep TEAMS_WEBHOOK_URL
```

<br>

****

<br>

# 3. Prometheus Component

```txt
Application/Kubernetes components expose metrics
⬇️
Prometheus scrapes and stores metrics
⬇️
PrometheusRule defines alert condition
⬇️
Prometheus evaluates those rules
⬇️
If condition is true, Prometheus fire an alert
⬇️
Alertmanager receives the alert
⬇️
AlertmanagerConfig tells Alertmanager where to send matching alerts
⬇️
Receiver gets notification
⬇️
In this project: AI summarizer ➡️ Teams Workflow card

```

## 3.1. PrometheusRule

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: ai-summarizer-test-alert
  namespace: monitoring
  labels:
    release: prometheus
spec:
  groups:
    - name: ai-summarizer-test.rules
      rules:
        - alert: AISummarizerTestAlert
          expr: vector(1)
          for: 30s
          labels:
            severity: warning
            ai_summarizer: "true"
            namespace: monitoring
            pod: test-pod
          annotations:
            summary: "AI summarizer test alert"
            description: "This is a controlled test alert."
```

| Components                   | Desc                                                                                                                                                                                                                                                                                                                      |
|------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| metadata.labels              | Used by Prometheus Operator to decide where this PrometheusRule should be selected by your Prometheus instance.<br><br>Prometheus CR usually has a `ruleSelector`. If PrometheusRule does not have the expected label, Prometheus may ignore it.                                                                          |
| alert: AISummarizerTestAlert | Alert name. When the alert fires, Prometheus adds this as a label: `alertname="AISummarizerTestAlert"`.                                                                                                                                                                                                                   |
| expr: vector(1)              | PromQL condition. `vector(1)` is always true, this alert is intentionally always active.                                                                                                                                                                                                                                  |
| for: 30s                     | Expression must remain true for 30s before the alert becomes firing.                                                                                                                                                                                                                                                      |
| `labels` inside the rule     | These labels are attached to the alert payload. `ai_summarizer: "true"` is for AlertManagerConfig to decide if this alert go to the AI summarizer. `namespace: monitoring` matters because AlertManagerConfig is in the monitoring namespace, and the Prometheus Operator is applying namespace-scoped matching behavior. |
| annotations                  | Human-readable information                                                                                                                                                                                                                                                                                                |


## 3.2. Alertmanager

* Receives alerts from Prometheus.

Prometheus says: `AI SummarizerTestAlert is firing. Here are its labels and annotations.`

Alertmanager then decides:

```txt
Should I send this?
Where should I send it?
Should I group it with other alerts?
Should I suppress it?
Should I repeat it later?
Should I send a resolved notification when it clears?
```

<br>

## 3.3. AlertmanagerConfig

Instead of manually editing Alertmanager's config secret, we can define routing like this:

```yaml
apiVersion: monitoring.coreos.com/v1alpha1
kind: AlertmanagerConfig
metadata:
  name: ai-incident-summarizer
  namespace: monitoring
  labels:
    release: prometheus
spec:
  route:
    receiver: ai-incident-summarizer
    matchers:
      - name: ai_summarizer
        value: "true"
        matchType: "="
    groupBy:
      - alertname
      - namespace
      - pod
    groupWait: 10s
    groupInterval: 1m
    repeatInterval: 5m
  receivers:
    - name: ai-incident-summarizer
      webhookConfigs:
        - url: http://ai-incident-summarizer.ai.svc:8000/webhook/alertmanager
          sendResolved: true
```

| Components         | desc                                                                                                                                                                                                                      |
|--------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `metadata.labels`  | Lets Alertmanager select this AlertmanagerConfig.                                                                                                                                                                         |
| `route.receiver`   | This is saying: `If an alert matches this route, send it to the receiver named ai-incident-summarizer`.                                                                                                                   |
| `matchers`         | Only alerts with `ai_summarizer="true"` should match this route.                                                                                                                                                          |
| `groupBy`          | This tells Alertmanager how to group alerts together. Alerts with the same values for those labels can be grouped into one notification.<br>This prevents Alertmanager from spamming one message per alert instance.      |
| `groupWait: 10s`   | This means, when a new alert group appears, wait 10s before sending the first notification. The wait is because more related alerts may arrive shortly after, and Alertmanager can group them together.                   |
| groupInterval: 1m  | This means, if new alerts are added to an existing group, wait at least 1 minute before sending another notification for that group.                                                                                      |
| repeatInteral: 5m  | This means, if the alert remains firing, send a repeat notification every 5 minutes.                                                                                                                                      |
| webhookConfigs.url | Where Alertmanager sends the alert payload.<br><br>Alertmanager sneds an HTTP POST to `http://ai-incident-summarizer.ai.svc:8000/webhook/alertmanager`, FastAPI app receives that at `@app.post("/webhook/alertmanager")` |
| sendResolved       | This means Alertmanager will notify your summarizer when the alert is resolved.                                                                                                                                           |

<br><br>

# 4. Ollama LLM (For learning)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start server
ollama serve

# Verify Ollama is running
curl http://localhost:11434/api/tags

# Pull a small model
ollama pull gemma3:4b

# Interactive test. Ask something simple: Explain CrashLoopBackOff in one sentence.
ollama run gemma3:4b

# Exit interactive mode
/bye
```

## 4.1. Test Ollama API

```bash
curl http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma3:4b",
    "stream": false,
    "messages": [
      {
        "role": "system",
        "content": "You are an experienced Kubernetes SRE."
      },
      {
        "role": "user",
        "content": "A pod is in CrashLoopBackOff and its previous logs say connection refused. Give a likely cause and two next actions."
      }
    ]
  }'
```

* Use `"stream": false` for one complete JSON response, easier to process.

## 4.2. Allow Minikube to reach Ollama

```bash
# By default Ollama may only listen on localhost. Configure it to listen on all host interfaces
export OLLAMA_HOST=0.0.0.0:11434
ollama serve

# Verify listening address
ss -ltnp | grep 11434
```

* Minikube provide the following host name: `host.minikube.internal`.

<br><br>