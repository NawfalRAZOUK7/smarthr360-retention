"""Module 5 tests: detection rules, end-to-end retention flow, authorization."""

import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, override_settings

from smarthr360_jwt_auth import conf

from ..models import Action, Employee, Signal
from ..services.detection import RiskDetectionService

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_PEM = _key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
PUBLIC_PEM = (
    _key.public_key()
    .public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)


def bearer(user_id=1, role="HR"):
    token = jwt.encode(
        {
            "token_type": "access",
            "user_id": user_id,
            "email": f"u{user_id}@corp.com",
            "role": role,
            "groups": [],
            "iss": "smarthr360",
            "exp": int(time.time()) + 300,
        },
        PRIVATE_PEM,
        algorithm="RS256",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


class BaseCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._s = override_settings(
            SMARTHR_JWT_AUTH={"PUBLIC_KEY": PUBLIC_PEM, "ISSUER": "smarthr360"}
        )
        cls._s.enable()
        conf.clear_cache()

    @classmethod
    def tearDownClass(cls):
        cls._s.disable()
        conf.clear_cache()
        super().tearDownClass()


class DetectionRuleTests(BaseCase):
    def test_low_engagement_detected(self):
        emp = Employee.objects.create(
            employee_id="E1", name="Sam", email="s@c.com", engagement_score=40
        )
        signal = RiskDetectionService.detect_risk(emp)
        self.assertEqual(signal.signal_type, "low_engagement")
        self.assertEqual(signal.intensity, 60)

    def test_high_absence_detected(self):
        emp = Employee.objects.create(
            employee_id="E2", name="Ana", email="a@c.com", absence_days_90d=12
        )
        signal = RiskDetectionService.detect_risk(emp)
        self.assertEqual(signal.signal_type, "high_absence")

    def test_healthy_employee_no_signal(self):
        emp = Employee.objects.create(
            employee_id="E3", name="Ok", email="o@c.com",
            engagement_score=90, performance_score=80,
        )
        self.assertIsNone(RiskDetectionService.detect_risk(emp))


class RetentionFlowTests(BaseCase):
    def setUp(self):
        self.at_risk = Employee.objects.create(
            user_id=42, employee_id="E10", name="Youssef",
            email="y@c.com", engagement_score=35,
        )
        Employee.objects.create(
            user_id=43, employee_id="E11", name="Sara",
            email="sa@c.com", engagement_score=95, performance_score=90,
        )

    def test_full_flow_detect_chat_action_review(self):
        # 1. HR runs detection -> conversation opened for the at-risk employee
        resp = self.client.post("/api/retention/detect/", **bearer(1, "HR"))
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertEqual(body["at_risk_count"], 1)
        conv_id = body["results"][0]["conversation_id"]
        self.assertIn("Youssef", body["results"][0]["opening_message"])

        # 2. The employee replies (keyword fallback -> 'salary')
        reply = self.client.post(
            f"/api/retention/conversations/{conv_id}/respond/",
            {"message": "Je ne suis pas satisfait de mon salaire depuis deux ans."},
            content_type="application/json",
            **bearer(42, "EMPLOYEE"),
        )
        self.assertEqual(reply.status_code, 200, reply.content)
        self.assertEqual(reply.json()["identified_need"], "salary")
        action_id = reply.json()["action"]["id"]
        self.assertEqual(reply.json()["action"]["priority"], "high")

        # signal resolved by the conversation
        self.assertTrue(Signal.objects.get().resolved)

        # 3. HR reviews the proposed action
        review = self.client.post(
            f"/api/retention/actions/{action_id}/review/",
            {"status": "approved"},
            content_type="application/json",
            **bearer(1, "HR"),
        )
        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.json()["status"], "approved")
        self.assertEqual(Action.objects.get().reviewed_by_user_id, 1)

    def test_employee_cannot_touch_other_conversations(self):
        self.client.post("/api/retention/detect/", **bearer(1, "HR"))
        conv_id = self.at_risk.conversations.get().id
        resp = self.client.post(
            f"/api/retention/conversations/{conv_id}/respond/",
            {"message": "hello"},
            content_type="application/json",
            **bearer(43, "EMPLOYEE"),  # Sara, not the at-risk employee
        )
        self.assertEqual(resp.status_code, 404)  # scoped queryset hides it

    def test_hr_gates(self):
        for method, url in (
            ("post", "/api/retention/detect/"),
            ("get", "/api/retention/signals/"),
            ("get", "/api/retention/employees/"),
            ("get", "/api/retention/actions/"),
        ):
            resp = getattr(self.client, method)(url, **bearer(9, "EMPLOYEE"))
            self.assertEqual(resp.status_code, 403, url)


class SignalIngestTests(BaseCase):
    """Cross-service signal intake (e.g. workload burnout alerts)."""

    def test_self_report_creates_signal_and_conversation(self):
        resp = self.client.post(
            "/api/retention/signals/ingest/",
            {"user_id": 77, "signal_type": "burnout_risk", "intensity": 86,
             "source": "smarthr360-workload"},
            content_type="application/json",
            **bearer(77, "EMPLOYEE"),
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertIn("charge de travail", body["opening_message"])
        emp = Employee.objects.get(user_id=77)
        self.assertEqual(emp.signals.get().signal_type, "burnout_risk")

    def test_dedupe_open_signal(self):
        for _ in range(2):
            resp = self.client.post(
                "/api/retention/signals/ingest/",
                {"user_id": 78, "signal_type": "burnout_risk", "intensity": 90},
                content_type="application/json",
                **bearer(78, "EMPLOYEE"),
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["deduplicated"])
        self.assertEqual(Employee.objects.get(user_id=78).signals.count(), 1)

    def test_employee_cannot_report_others(self):
        resp = self.client.post(
            "/api/retention/signals/ingest/",
            {"user_id": 99, "signal_type": "burnout_risk", "intensity": 90},
            content_type="application/json",
            **bearer(78, "EMPLOYEE"),
        )
        self.assertEqual(resp.status_code, 403)

    def test_manager_can_report_team_member(self):
        resp = self.client.post(
            "/api/retention/signals/ingest/",
            {"user_id": 99, "signal_type": "burnout_risk", "intensity": 75},
            content_type="application/json",
            **bearer(5, "MANAGER"),
        )
        self.assertEqual(resp.status_code, 201)

    def test_invalid_type_rejected(self):
        resp = self.client.post(
            "/api/retention/signals/ingest/",
            {"user_id": 78, "signal_type": "bad_vibes", "intensity": 50},
            content_type="application/json",
            **bearer(78, "EMPLOYEE"),
        )
        self.assertEqual(resp.status_code, 400)
