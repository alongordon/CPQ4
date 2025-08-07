"""Tests for the ``edit_OCC`` application."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from upload_STEP.models import StepFile


class OccDocumentAdminTests(TestCase):
    """Tests ensuring the OCC document admin interface works."""

    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username="admin", email="admin@example.com", password="password"
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_changelist_accessible(self) -> None:
        url = reverse("admin:edit_OCC_occdocument_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    @patch("upload_STEP.admin.create_occ_document")
    def test_build_occ_document_action_called(self, mock_create) -> None:
        step_file = StepFile.objects.create(
            file=SimpleUploadedFile("sample.stp", b"dummy data")
        )
        url = reverse("admin:upload_STEP_stepfile_changelist")
        data = {
            "action": "build_occ_document_action",
            "_selected_action": [str(step_file.pk)],
        }
        self.client.post(url, data, follow=True)
        mock_create.assert_called_once_with(step_file)

