import unittest

from src.campaign_service import CampaignRequest, InfraiClient, PlayerAsset, deliver_approved_asset


class RecordingClient(InfraiClient):
    def __init__(self):
        super().__init__("test-key")
        self.sent = []

    def send_campaign(self, request):
        self.sent.append(request)
        return {"ok": True, "data": {"message_id": "msg-test"}}


class CampaignDecisionTests(unittest.TestCase):
    def test_pending_player_asset_stays_out_of_the_send_queue(self):
        client = RecordingClient()
        request = CampaignRequest("player@example.com", PlayerAsset("p1", "Sky Ship", "pending"), "season-1")
        result = deliver_approved_asset(client, request)
        self.assertEqual(result.reason, "awaiting moderation")
        self.assertFalse(result.sent)
        self.assertEqual(client.sent, [])

    def test_approved_player_asset_returns_message_id(self):
        client = RecordingClient()
        request = CampaignRequest("player@example.com", PlayerAsset("p1", "Sky Ship", "approved"), "season-1")
        result = deliver_approved_asset(client, request)
        self.assertTrue(result.sent)
        self.assertEqual(result.message_id, "msg-test")


if __name__ == "__main__":
    unittest.main()
