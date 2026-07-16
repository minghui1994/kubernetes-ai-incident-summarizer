from fastapi import FastAPI

from app.models import AlertManagerWebhook
from app.summarizer import summarize_alert
from app.teams import TeamsWebhookNotConfiguredError, send_to_teams

app = FastAPI(
    title = "AI Incident Summarizer",
    description="Receives Alertmanager webhooks and generates incident summaries",
    version="0.1.0"
)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/webhook/alertmanager")
async def receive_alertmanager_webhook(payload: AlertManagerWebhook) -> dict:
    # await because prometheus context uses prometheus_client, which uses httpx.AsyncClient
    summary = await summarize_alert(payload)

    # For now, print the summary to stdout
    # Later, will send to Microsoft Teams
    print(summary)

    try:
        await send_to_teams(summary)
        teams_status = "sent"
    except TeamsWebhookNotConfiguredError:
        teams_status = "skipped_not_configured"

    return {
        "status": "received",
        "alert_count": len(payload.alerts),
        "teams_status": teams_status,
        "summary": summary
    }