from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class HermeticRunner(DiscoverRunner):
    """Tests never inherit the contributor's LOCAL_AUTO_LOGIN from .env: `make dev` sets it, and
    an automatic sign-in would change responses and query counts. Tests that need it opt in
    with override_settings."""

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._no_auto_login = override_settings(LOCAL_AUTO_LOGIN="")
        self._no_auto_login.enable()

    def teardown_test_environment(self, **kwargs):
        self._no_auto_login.disable()
        super().teardown_test_environment(**kwargs)
