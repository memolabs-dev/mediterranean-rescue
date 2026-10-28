from catalog.sheets import load_contract
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.cache import patch_vary_headers


class PublicFrontendCors:
    """Opt-in CORS for read-only public API; private routes never receive CORS.

    Cross-origin contributor/admin access intentionally remains unsupported. Deploy a
    same-origin reverse proxy for another team's private frontend instead.
    """

    METHODS = {"GET", "HEAD"}
    HEADERS = {"accept", "content-type"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/v1/"):
            return self.get_response(request)

        origin = request.headers.get("Origin")
        allowed = bool(origin and origin in settings.PUBLIC_FRONTEND_ORIGINS)
        preflight_method = request.headers.get("Access-Control-Request-Method")

        if request.method == "OPTIONS" and preflight_method:
            raw_headers = request.headers.get("Access-Control-Request-Headers", "")
            headers = {header.strip().lower() for header in raw_headers.split(",") if header.strip()}
            if (
                not allowed
                or preflight_method not in self.METHODS
                or not headers.issubset(self.HEADERS)
            ):
                response = HttpResponse(status=403)
            else:
                response = HttpResponse(status=204)
                response["Access-Control-Allow-Origin"] = origin
                response["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
                response["Access-Control-Allow-Headers"] = "Accept, Content-Type"
                response["Access-Control-Max-Age"] = "600"
            patch_vary_headers(response, ("Origin",))
            return response

        response = self.get_response(request)
        if origin:
            patch_vary_headers(response, ("Origin",))
            if allowed and request.method in self.METHODS:
                response["Access-Control-Allow-Origin"] = origin
        return response


API_BODY_LIMIT = 65536
# Export uploads carry a whole CSV: the contract limit plus room for the form fields.
UPLOAD_PATHS = ("/api/private/v1/imports/", "/api/private/v1/imports/diagnose/")
UPLOAD_OVERHEAD = 65536


class APIRequestLimit:
    """Refuses oversized API requests from the declared length, before any body is read."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.upload_limit = load_contract()["input"]["max_bytes"] + UPLOAD_OVERHEAD

    def __call__(self, request):
        if request.path.startswith("/api/"):
            limit = self.upload_limit if request.path in UPLOAD_PATHS else API_BODY_LIMIT
            length = request.headers.get("Content-Length") or "0"
            if (
                not length.isdigit()
                or int(length) > limit
                or len(request.get_full_path().encode()) > API_BODY_LIMIT
            ):
                return JsonResponse({"code": "http_413", "detail": "Request too large"}, status=413)
        return self.get_response(request)


# Everything the site needs comes from its own origin: the map draws a local land outline, no
# tiles, fonts or scripts from elsewhere. MapLibre starts its workers from blob: URLs and sets
# inline styles; nothing evaluates strings as code.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "worker-src 'self' blob:",
        "child-src blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


class ContentSecurityPolicy:
    """Sets the site's Content-Security-Policy on every response (audit of 25 October 2026)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.setdefault("Referrer-Policy", "same-origin")
        return response


LOCAL_AUTO_LOGIN_OFF = "local_auto_login_off"


def local_auto_login_user():
    """The account LOCAL_AUTO_LOGIN names, when it may be signed in this way, else None."""
    from django.conf import settings
    from django.contrib.auth import get_user_model

    if not settings.LOCAL_AUTO_LOGIN:
        return None
    return (
        get_user_model()
        .objects.filter(
            username=settings.LOCAL_AUTO_LOGIN, is_active=True, is_staff=False, is_superuser=False
        )
        .first()
    )


class LocalAutoLogin:
    """Development only: signs every visitor in as LOCAL_AUTO_LOGIN, so the team space opens
    without a sign-in screen on a local machine. Settings refuse it outside development, and a
    staff or superuser account is never signed in this way: whoever reaches the dev server (a
    tunnel, a private network) would hold the admin (security audit of 25 October 2026)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.contrib.auth import login

        # A person who signed out stays signed out in this browser (Guillaume, 25 October 2026):
        # otherwise the next request would sign them straight back in.
        if not request.user.is_authenticated and request.COOKIES.get(LOCAL_AUTO_LOGIN_OFF) != "1":
            user = local_auto_login_user()
            if user is not None:
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return self.get_response(request)
