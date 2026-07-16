import os

import httpx


class TeamsWebhookNotConfiguredError(Exception):
    pass


def get_teams_webhook_url() -> str:
    webhook_url = os.getenv("TEAMS_WEBHOOK_URL")

    if not webhook_url:
        raise TeamsWebhookNotConfiguredError(
            "TEAMS_WEBHOOK_URL environment variable is not configured."
        )

    return webhook_url


def build_teams_message(summary: str) -> dict:
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "🚨 AI Incident Summary",
                            "weight": "Bolder",
                            "size": "Large",
                        },
                        {
                            "type": "TextBlock",
                            "text": summary,
                            "wrap": True,
                        },
                    ],
                },
            }
        ],
    }


async def send_to_teams(summary: str) -> None:
    webhook_url = get_teams_webhook_url()
    message = build_teams_message(summary)

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=message)
        response.raise_for_status()
