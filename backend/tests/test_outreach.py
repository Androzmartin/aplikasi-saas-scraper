"""Outreach draft generation and send tracking (P2)."""
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from bson import ObjectId

from app.services.outreach import CHANNELS, TONES, build_draft, pitch_points

pytestmark = pytest.mark.asyncio

LEAD = {
    "business_name": "Warung Kopi Senja",
    "contact_person": "Budi Santoso",
    "whatsapp_number": "+6281234567890",
    "phone_number": "+62217220091",
    "email": "halo@kopisenja.co.id",
    "region": "jakarta_selatan",
    "audit_score": 34,
}
AUDIT = {
    "score": 34,
    "issues": [
        {"code": "no_viewport", "severity": "high"},
        {"code": "legacy_markup", "severity": "high"},
        {"code": "no_cta", "severity": "high"},
        {"code": "no_email", "severity": "low"},
        {"code": "no_navigation", "severity": "low"},
    ],
}


class TestPitchPoints:
    async def test_high_severity_findings_come_first_and_are_capped(self):
        points = pitch_points(AUDIT)
        assert len(points) == 3
        assert "layar HP" in points[0]

    async def test_unknown_codes_are_skipped(self):
        points = pitch_points({"issues": [{"code": "kode-asing", "severity": "high"}]})
        assert points == []

    async def test_no_audit_yields_nothing(self):
        assert pitch_points(None) == []


class TestDraftContent:
    @pytest.mark.parametrize("channel", CHANNELS)
    @pytest.mark.parametrize("tone", TONES)
    async def test_every_combination_produces_a_usable_draft(self, channel, tone):
        draft = build_draft(LEAD, AUDIT, channel, tone, "Andi", "Agency Nusantara")
        assert draft.message.strip()
        assert "Warung Kopi Senja" in draft.message
        assert "Andi" in draft.message
        assert draft.send_url

    async def test_uses_the_contact_person_when_known(self):
        assert "Budi Santoso" in build_draft(LEAD, AUDIT, "whatsapp", "formal").message

    async def test_falls_back_gracefully_without_a_contact_person(self):
        lead = dict(LEAD)
        lead.pop("contact_person")
        message = build_draft(lead, AUDIT, "whatsapp", "formal").message
        assert "Warung Kopi Senja" in message
        assert "None" not in message

    async def test_acronyms_keep_their_case(self):
        """'HP' must not be lowercased by naive capitalisation."""
        message = build_draft(LEAD, AUDIT, "whatsapp", "formal").message
        assert "layar HP" in message
        assert "layar hp" not in message

    async def test_mentions_the_audit_score_when_available(self):
        assert "34/100" in build_draft(LEAD, AUDIT, "whatsapp", "formal").message

    async def test_falls_back_to_the_stored_score_without_an_audit_doc(self):
        # No audit document, but the lead carries a score from the last scrape.
        draft = build_draft(LEAD, None, "whatsapp", "formal")
        assert "34/100" in draft.message

    async def test_omits_the_score_line_when_nothing_is_scored(self):
        lead = {k: v for k, v in LEAD.items() if k != "audit_score"}
        draft = build_draft(lead, None, "whatsapp", "formal")
        assert "/100" not in draft.message
        assert "Warung Kopi Senja" in draft.message

    async def test_email_has_a_subject_and_whatsapp_does_not(self):
        assert build_draft(LEAD, AUDIT, "email", "formal").subject
        assert build_draft(LEAD, AUDIT, "whatsapp", "formal").subject is None

    async def test_rejects_unknown_channel_and_tone(self):
        with pytest.raises(ValueError):
            build_draft(LEAD, AUDIT, "telegram", "formal")
        with pytest.raises(ValueError):
            build_draft(LEAD, AUDIT, "whatsapp", "puitis")


class TestDeepLinks:
    async def test_whatsapp_link_carries_the_exact_message(self):
        draft = build_draft(LEAD, AUDIT, "whatsapp", "formal", "Andi")
        assert draft.send_url.startswith("https://wa.me/6281234567890?text=")
        encoded = parse_qs(urlparse(draft.send_url).query)["text"][0]
        assert encoded == draft.message

    async def test_mailto_link_carries_subject_and_body(self):
        draft = build_draft(LEAD, AUDIT, "email", "formal", "Andi")
        assert draft.send_url.startswith("mailto:halo@kopisenja.co.id?")
        params = parse_qs(urlparse(draft.send_url).query)
        assert params["subject"][0] == draft.subject
        assert params["body"][0] == draft.message

    async def test_falls_back_to_phone_when_no_whatsapp(self):
        lead = dict(LEAD)
        lead.pop("whatsapp_number")
        draft = build_draft(lead, AUDIT, "whatsapp", "formal")
        assert draft.recipient == LEAD["phone_number"]

    async def test_no_link_when_there_is_no_recipient(self):
        lead = {"business_name": "Tanpa Kontak", "region": "bogor"}
        draft = build_draft(lead, AUDIT, "whatsapp", "formal")
        assert draft.send_url is None
        assert draft.message.strip()  # the text is still useful to copy


class TestOutreachApi:
    @pytest.fixture
    async def lead_id(self, auth_client, mock_db):
        project = (
            await auth_client.post(
                "/api/projects", json={"name": "Proyek Outreach", "target_region": "jakarta_selatan"}
            )
        ).json()
        me = (await auth_client.get("/api/auth/me")).json()
        tenant_id = ObjectId(me["tenant"]["id"])
        lead = await mock_db.leads.insert_one(
            {
                "project_id": ObjectId(project["id"]),
                "tenant_id": tenant_id,
                "website_url": "https://warungkopisenja.co.id/",
                **{k: v for k, v in LEAD.items()},
                "status": "new",
                "tags": [],
                "created_at": datetime.now(timezone.utc),
            }
        )
        await mock_db.website_audits.insert_one(
            {"lead_id": lead.inserted_id, "tenant_id": tenant_id, **AUDIT,
             "created_at": datetime.now(timezone.utc)}
        )
        return str(lead.inserted_id)

    async def test_draft_endpoint_personalises_with_the_tenant(self, auth_client, lead_id):
        response = await auth_client.get(f"/api/outreach/{lead_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["channel"] == "whatsapp"
        assert "Budi Santoso" in body["message"]
        assert "Agency Nusantara" in body["message"]  # tenant company name
        assert "Budi Santoso" in body["message"]
        assert body["send_url"].startswith("https://wa.me/")

    async def test_channel_and_tone_are_selectable(self, auth_client, lead_id):
        email = await auth_client.get(f"/api/outreach/{lead_id}?channel=email&tone=ramah")
        assert email.status_code == 200
        assert email.json()["subject"]
        assert email.json()["send_url"].startswith("mailto:")

    async def test_bad_channel_is_rejected(self, auth_client, lead_id):
        assert (await auth_client.get(f"/api/outreach/{lead_id}?channel=sms")).status_code == 400

    async def test_mark_sent_advances_a_new_lead(self, auth_client, lead_id):
        response = await auth_client.post(f"/api/outreach/{lead_id}/mark-sent?channel=whatsapp")
        assert response.status_code == 200
        assert response.json()["status"] == "contacted"

        lead = (await auth_client.get(f"/api/leads/{lead_id}")).json()
        assert lead["status"] == "contacted"
        assert lead["outreach_channel"] == "whatsapp"
        assert lead["outreach_sent_at"]

    async def test_mark_sent_never_downgrades_a_later_stage(self, auth_client, lead_id):
        await auth_client.patch(f"/api/leads/{lead_id}", json={"status": "qualified"})
        await auth_client.post(f"/api/outreach/{lead_id}/mark-sent?channel=email")
        lead = (await auth_client.get(f"/api/leads/{lead_id}")).json()
        assert lead["status"] == "qualified"
        assert lead["outreach_channel"] == "email"

    async def test_mark_sent_is_written_to_the_audit_log(self, auth_client, lead_id, mock_db):
        await auth_client.post(f"/api/outreach/{lead_id}/mark-sent?channel=whatsapp")
        log = await mock_db.activity_logs.find_one({"action": "outreach_sent"})
        assert log is not None and log["detail"] == "whatsapp"

    async def test_other_tenants_cannot_draft_for_this_lead(self, client, lead_id):
        other = await client.post(
            "/api/auth/register",
            json={"company_name": "Agency Lain", "name": "Cici",
                  "email": "cici@lain.co.id", "password": "password-lain-123"},
        )
        token = other.json()["access_token"]
        response = await client.get(
            f"/api/outreach/{lead_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404
