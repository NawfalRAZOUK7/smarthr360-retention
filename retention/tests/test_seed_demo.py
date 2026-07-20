from django.core.management import call_command
from django.test import TestCase

from retention.models import Action, AttritionForecast, Employee


class SeedDemoTests(TestCase):
    def test_seed_demo_is_idempotent(self):
        call_command("seed_demo")
        first = (Employee.objects.count(), AttritionForecast.objects.count(), Action.objects.count())
        call_command("seed_demo")
        self.assertEqual((Employee.objects.count(), AttritionForecast.objects.count(), Action.objects.count()), first)
