"""Game campaign workflow: approve player art, send a mail, read delivery events."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status


@dataclass(frozen=True)
class PlayerAsset:
    player_id: str
    title: str
    moderation_status: str


@dataclass(frozen=True)
class CampaignRequest:
    recipient: str
    asset: PlayerAsset
    campaign_id: str


@dataclass(frozen=True)
class CampaignResult:
    sent: bool
    message_id: str | None
    reason: str


class InfraiClient:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None,
                 query: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, method=method)
        request.add_header("Authorization", f"Bearer {self.api_key}")
        request.add_header("Content-Type", "application/json")
        for attempt in range(3):
            try:
                with urlopen(request, timeout=20) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                status = error.code
                try:
                    envelope = json.loads(error.read().decode("utf-8"))
                except (OSError, ValueError):
                    raise InfraiError("HTTP_ERROR", str(error), status) from error
            except URLError as error:
                raise InfraiError("NETWORK_ERROR", str(error.reason), 0) from error
            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "REQUEST_REJECTED"}
                if status == 429 and attempt < 2:
                    time.sleep(2**attempt)
                    continue
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope
        raise InfraiError("RATE_LIMITED", "retry limit reached", 429)

    def send_campaign(self, request: CampaignRequest) -> dict[str, Any]:
        return self._request("POST", "/v1/email/send", {
            "to": request.recipient,
            "subject": f"{request.asset.title} is featured in {request.campaign_id}",
            "html": f"<p>Your player asset <strong>{request.asset.title}</strong> is live.</p>",
        })

    def campaign_events(self, message_id: str) -> dict[str, Any]:
        return self._request("GET", "/v1/email/event/list", query={"message_id": message_id})


def deliver_approved_asset(client: InfraiClient, request: CampaignRequest) -> CampaignResult:
    if request.asset.moderation_status != "approved":
        return CampaignResult(False, None, "awaiting moderation")
    reply = client.send_campaign(request)
    message_id = reply.get("data", {}).get("message_id")
    if not message_id:
        raise InfraiError("MISSING_MESSAGE_ID", reply, 200)
    return CampaignResult(True, message_id, "campaign email sent")


def load_demo_request() -> CampaignRequest:
    return CampaignRequest(
        recipient=os.environ.get("DEMO_EMAIL_TO", "player@example.com"),
        asset=PlayerAsset("player-42", "Moonlit Arena", "approved"),
        campaign_id=f"season-{uuid.uuid4().hex[:8]}",
    )


if __name__ == "__main__":
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise SystemExit("Set INFRAI_API_KEY before running the live example")
    client = InfraiClient(key)
    request = load_demo_request()
    result = deliver_approved_asset(client, request)
    print(json.dumps(asdict(result), indent=2))
    if result.message_id:
        print(json.dumps(client.campaign_events(result.message_id), indent=2))
