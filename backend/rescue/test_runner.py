from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class HermeticRunner(DiscoverRunner):
    """Tests never inherit the contributor's .env choices that `make dev` sets: an automatic
    sign-in would change responses and query counts, and training mode would hide the published
    sources production shows. Tests that need either opt in with override_settings."""

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._as_production = override_settings(LOCAL_AUTO_LOGIN="", DATA_MODE="production")
        self._as_production.enable()

    def teardown_test_environment(self, **kwargs):
        self._as_production.disable()
        super().teardown_test_environment(**kwargs)
