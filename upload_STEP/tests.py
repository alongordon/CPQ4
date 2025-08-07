"""Tests for the ``upload_STEP`` application."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class AdminInterfaceTests(TestCase):
    """Tests related to the Django admin interface."""

    def setUp(self) -> None:
        """Create a superuser and log them in for admin tests."""
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username="admin", email="admin@example.com", password="password"
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_build_occ_button_present(self) -> None:
        """Ensure the ``Build OCC file`` button is rendered on the changelist."""
        url = reverse("admin:upload_STEP_stepfile_changelist")
        response = self.client.get(url)
        self.assertContains(response, "Build OCC file")
