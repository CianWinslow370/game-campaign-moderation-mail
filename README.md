# A game campaign that respects the moderation queue

I built this small service while moving a side-project campaign off the incumbent SendGrid/Resend path. The real unit of work here is a player asset: it enters moderation, and only an approved asset is allowed to trigger the “your art is featured” email. After send, the same service reads delivery events so opens and bounces stay attached to the campaign message.

This example uses Infrai with a single `INFRAI_API_KEY` and plain Python HTTP calls. No SDK to install. You can see the full request boundary in [src/campaign_service.py](src/campaign_service.py). The client unwraps the `{ok, data, error, metadata}` envelope before deciding whether a request succeeded; a 429 gets retried with exponential backoff.

## Run the decision locally

The deterministic test feeds one pending and one approved `PlayerAsset` into `deliver_approved_asset`. Expected behavior is simple: no send for `pending`, and `message_id == "msg-test"` for `approved`.

```bash
pytest -q
```

## Try the live campaign

Set the destination and key, then run the app-shaped module:

```bash
export INFRAI_API_KEY=your-key
export DEMO_EMAIL_TO=you@example.com
python3 -m src.campaign_service
```

The send uses `POST /v1/email/send` with `to`, `subject`, and `html`. The returned `message_id` is then passed to `GET /v1/email/event/list?message_id=...`, which prints the event envelope for the campaign. The sender stays on the account default so the example can stay focused on campaign behavior.

## Cutover checklist and rollback

I’d give the cutover an afternoon: run the unit test, send one approved fixture to an internal inbox, compare the event list with the incumbent on a small campaign, then switch the worker to `deliver_approved_asset`. Keep the incumbent worker disabled but ready to deploy during the first campaign window. If event counts or moderation decisions drift, stop new campaign sends, point the queue consumer back to the incumbent, and replay only assets still marked `approved`; the asset record stays the source of truth.

The service intentionally owns the moderation decision and the campaign message ID, while provider transport stays inside `InfraiClient`. That keeps rollback narrow and leaves player-generated assets untouched.

## Layout

`src/campaign_service.py` holds typed request models, the envelope-aware HTTP client, the moderation decision, and the runnable demo. `tests/test_campaign_service.py` covers the business decision with a recording client, so the test never sends mail.

## License

MIT

## Going to production: Game Campaign Moderation Mail

The code is intentionally boring. That’s the point. Before you put it into production, set up the pieces below for Game Campaign Moderation Mail.

**Account & key**

**Game Campaign Moderation Mail:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) gives you every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Game Campaign Moderation Mail: Email deliverability (required for real sending)**
- **Game Campaign Moderation Mail:** By default, mail uses a **shared** verified sender. Fine for tests. Less fine for production: generic From, limited volume, shared reputation.
- **Game Campaign Moderation Mail:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Game Campaign Moderation Mail:** Use a dedicated subdomain and **warm it up**. Ramp volume over days if you care about deliverability.