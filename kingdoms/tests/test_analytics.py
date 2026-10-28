from django.test import TestCase, override_settings
from django.urls import reverse

ENDPOINT = "https://stats.example.com/count"
REDACTION = "[0-9a-fA-F]{64}"


@override_settings(GOATCOUNTER_URL="")
class AnalyticsOffTests(TestCase):
    def test_page_has_no_tracking_script_by_default(self):
        response = self.client.get(reverse("kingdoms:home"))
        self.assertNotContains(response, "goatcounter")
        self.assertNotContains(response, "count.js")


@override_settings(GOATCOUNTER_URL=ENDPOINT)
class AnalyticsOnTests(TestCase):
    def test_page_loads_script_from_endpoint(self):
        response = self.client.get(reverse("kingdoms:home"))
        self.assertContains(response, f'data-goatcounter="{ENDPOINT}"')
        self.assertContains(response, f'src="{ENDPOINT}.js"')

    def test_path_is_prefixed_with_hostname_and_redacts_access_codes(self):
        response = self.client.get(reverse("kingdoms:home"))
        self.assertContains(response, "location.hostname + location.pathname")
        self.assertContains(response, REDACTION)

    def test_footer_mentions_counting(self):
        response = self.client.get(reverse("kingdoms:home"))
        self.assertContains(response, "Anonymous page views are counted")
