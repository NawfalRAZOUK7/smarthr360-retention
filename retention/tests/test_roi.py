"""Tests for the retention cost-of-attrition / ROI view (loop-closer)."""

from django.test import TestCase, override_settings

from smarthr360_jwt_auth import conf

from ..models import Action, AttritionForecast, Conversation, Employee, Signal
from .test_retention_flow import PUBLIC_PEM, bearer


class RetentionROITests(TestCase):
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

    def setUp(self):
        self.emp = Employee.objects.create(
            employee_id="E-1", name="At Risk", email="a@corp.com", engagement_score=25
        )
        AttritionForecast.objects.create(
            employee=self.emp, risk_score=80.0, level=AttritionForecast.Level.HIGH,
            factors={}, signal_trend_per_day=0.1, top_drivers=["x"], rationale="",
            run_id="run-1",
        )
        # A recorded, successful outcome → realized savings.
        sig = Signal.objects.create(
            employee=self.emp, signal_type="low_engagement", intensity=70
        )
        conv = Conversation.objects.create(employee=self.emp, signal=sig)
        Action.objects.create(
            conversation=conv, employee=self.emp, description="1:1 + raise",
            priority="high", status="completed", employee_retained=True,
        )

    def test_roi_forward_and_realized(self):
        resp = self.client.get(
            "/api/retention/roi/?avg_replacement_cost=50000&action_cost=4000",
            **bearer(role="HR"),
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        # Forward: 80% risk * 50000 = 40000 exposure, all at-risk (HIGH).
        self.assertEqual(body["forward"]["total_exposure"], 40000)
        self.assertEqual(body["forward"]["at_risk_count"], 1)
        # Realized: 1 retained * (50000 - 4000) = 46000.
        self.assertEqual(body["realized"]["retained"], 1)
        self.assertEqual(body["realized"]["realized_savings"], 46000)
        self.assertEqual(body["realized"]["retention_rate"], 1.0)

    def test_roi_is_hr_gated(self):
        self.assertEqual(
            self.client.get("/api/retention/roi/", **bearer(role="EMPLOYEE")).status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/retention/roi/").status_code, 401)
