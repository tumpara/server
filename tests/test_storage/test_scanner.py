import shutil
import tempfile
from unittest import mock

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse
from selenium.webdriver.chrome.webdriver import WebDriver

from tumpara.accounts.models import User
from tumpara.storage.models import Library


class AdminTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def setUp(self):
        User.objects.create_superuser("test", "test@example.org", "test")
        self.client = Client()

        self.selenium.get(self.live_server_url + reverse("admin:login"))
        self.selenium.find_element_by_name("username").send_keys("test")
        self.selenium.find_element_by_name("password").send_keys("test")
        self.selenium.find_element_by_xpath('//input[@value="Log in"]').click()

        self.library = Library.objects.create(
            source=f"file://{tempfile.mkdtemp()}", context="storage"
        )

    def tearDown(self):
        shutil.rmtree(self.library.backend.base_location)
        super().tearDown()

    @mock.patch.object(Library, "scan")
    def test_library_scan_button(self, scan: mock.MagicMock):
        """Clicking the scan button in a library's admin page triggers the scan."""
        self.selenium.get(
            self.live_server_url
            + reverse("admin:storage_library_change", args=[self.library.pk])
        )
        self.selenium.find_element_by_xpath(
            '//input[@value="Scan this library"]'
        ).click()
        scan.assert_called_once()
