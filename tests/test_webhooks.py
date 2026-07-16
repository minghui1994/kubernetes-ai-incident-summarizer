from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_healthz_returns_ok():
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_accepts_complete_alertmanager_payload():
    payload = {
        "receiver": "ai-summarizer",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighPodRestartCount",
                    "severity": "warning",
                    "namespace": "default",
                    "pod": "crash-demo",
                },
                "annotations": {
                    "summary": "Pod has restarted",
                    "description": "Pod crash-demo in namespace default has restarted.",
                },
                "startsAt": "2026-05-13T01:00:00Z",
            }
        ],
        "groupLabels": {
            "alertname": "HighPodRestartCount",
        },
        "commonLabels": {
            "severity": "warning",
        },
        "commonAnnotations": {
            "summary": "Pod has restarted",
        },
        "externalURL": "http://alertmanager.example.com",
    }

    response = client.post("/webhook/alertmanager", json=payload)

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "received"
    assert body["alert_count"] == 1
    assert "Incident Summary" in body["summary"]
    assert "HighPodRestartCount" in body["summary"]
    assert "crash-demo" in body["summary"]
    assert "kubectl describe pod crash-demo -n default" in body["summary"]


def test_alertmanager_webhook_rejects_invalid_payload():
    payload = {
        "status": "firing",
        "alerts": []
    }

    response = client.post("/webhook/alertmanager", json=payload)

    assert response.status_code == 422


def test_webhook_skips_teams_when_webhook_is_not_configured():
    payload = {
        "receiver": "ai-summarizer",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighPodRestartCount",
                    "severity": "warning",
                    "namespace": "default",
                    "pod": "crash-demo",
                },
                "annotations": {
                    "summary": "Pod has restarted",
                    "description": "Pod crash-demo in namespace default has restarted.",
                },
                "startsAt": "2026-05-13T01:00:00Z",
            }
        ],
    }

    response = client.post("/webhook/alertmanager", json=payload)

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "received"
    assert body["alert_count"] == 1
    assert body["teams_status"] == "skipped_not_configured"
    assert "Incident Summary" in body["summary"]
    assert "HighPodRestartCount" in body["summary"]
    assert "crash-demo" in body["summary"]
    assert "kubectl describe pod crash-demo -n default" in body["summary"]
