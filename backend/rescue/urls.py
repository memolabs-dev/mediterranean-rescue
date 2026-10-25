from pathlib import Path

from catalog.api import EventsView, EventView, EvidenceView, MapPointsView, TimelineView
from catalog.private_api import (
    ExactCarriesView,
    IdentitiesView,
    MeView,
    ReviewDecisionView,
    ReviewRowsView,
    ReviewRowView,
    SessionView,
    SnapshotsView,
)
from catalog.private_history import HistoryView
from catalog.private_imports import (
    DiagnoseView,
    ImportDetailView,
    ImportOptionsView,
    ImportsView,
)
from catalog.private_invitations import (
    InvitationAcceptView,
    InvitationCheckView,
    InvitationsView,
    InvitationView,
)
from catalog.private_logbook import LogbookExportView, LogbookOverviewView
from catalog.private_ports import (
    PortLabelDecisionView,
    PortLabelsView,
    PortLabelView,
    PortsView,
    VesselsView,
)
from catalog.private_preview import (
    PreviewEventsView,
    PreviewEventView,
    PreviewMapView,
    PreviewTimelineView,
)
from catalog.private_publication import (
    PrepareView,
    PublicationDecisionView,
    PublicationEventsView,
    PublicationOverviewView,
)
from catalog.private_sync import SyncStatusView
from django.conf import settings
from django.contrib import admin
from django.db import connection
from django.http import FileResponse, Http404, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.urls import path, re_path
from django.views.decorators.http import require_GET, require_safe
from django.views.defaults import page_not_found
from drf_spectacular.views import SpectacularAPIView


@require_GET
def csrf(request):
    response = JsonResponse({"csrfToken": get_token(request)})
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


def admin_login(request):
    return redirect("/workspace")


def not_found(request, exception=None):
    """An unknown API address answers JSON like the rest of the API; others get Django's page."""
    if request.path.startswith("/api/"):
        return JsonResponse({"code": "http_404", "detail": "Not found"}, status=404)
    return page_not_found(request, exception)


handler404 = not_found


@require_safe
def frontend(request):
    """The application page for the frontend's own routes (/about, /workspace/…, /invite)."""
    if not settings.FRONTEND_DIST:
        raise Http404
    response = FileResponse(open(Path(settings.FRONTEND_DIST) / "index.html", "rb"))
    response["Content-Type"] = "text/html; charset=utf-8"
    # Always revalidated, so a new release reaches the next page load.
    response["Cache-Control"] = "no-cache"
    return response


urlpatterns = [
    # The admin has no attempt limit of its own: its sign-in form is replaced by the team
    # sign-in, which counts attempts per address (audit of 25 October 2026). Signed in as a
    # staff member, the admin opens as usual.
    path("admin/login/", admin_login),
    path("admin/", admin.site.urls),
    path("api/csrf/", csrf),
    path("api/health/", health),
    path("api/v1/events/", EventsView.as_view()),
    path("api/v1/events/<uuid:id>/", EventView.as_view()),
    path("api/v1/events/<uuid:id>/evidence/", EvidenceView.as_view()),
    path("api/v1/map-points/", MapPointsView.as_view()),
    path("api/v1/timeline/", TimelineView.as_view()),
    path("api/private/v1/me/", MeView.as_view()),
    path("api/private/v1/session/", SessionView.as_view()),
    path("api/private/v1/history/", HistoryView.as_view()),
    path("api/private/v1/invitations/", InvitationsView.as_view()),
    path("api/private/v1/invitations/check/", InvitationCheckView.as_view()),
    path("api/private/v1/invitations/accept/", InvitationAcceptView.as_view()),
    path("api/private/v1/invitations/<uuid:id>/", InvitationView.as_view()),
    path("api/private/v1/snapshots/", SnapshotsView.as_view()),
    path("api/private/v1/review/rows/", ReviewRowsView.as_view()),
    path("api/private/v1/review/rows/<uuid:id>/", ReviewRowView.as_view()),
    path("api/private/v1/review/rows/<uuid:id>/decision/", ReviewDecisionView.as_view()),
    path("api/private/v1/review/snapshots/<uuid:id>/exact-carries/", ExactCarriesView.as_view()),
    path("api/private/v1/review/identities/", IdentitiesView.as_view()),
    path("api/private/v1/imports/", ImportsView.as_view()),
    path("api/private/v1/imports/options/", ImportOptionsView.as_view()),
    path("api/private/v1/imports/diagnose/", DiagnoseView.as_view()),
    path("api/private/v1/imports/<uuid:id>/", ImportDetailView.as_view()),
    path("api/private/v1/ports/", PortsView.as_view()),
    path("api/private/v1/ports/labels/", PortLabelsView.as_view()),
    path("api/private/v1/ports/labels/<str:id>/", PortLabelView.as_view()),
    path("api/private/v1/ports/labels/<str:id>/decision/", PortLabelDecisionView.as_view()),
    path("api/private/v1/vessels/", VesselsView.as_view()),
    path("api/private/v1/publication/", PublicationOverviewView.as_view()),
    path("api/private/v1/publication/prepare/", PrepareView.as_view()),
    path("api/private/v1/publication/events/", PublicationEventsView.as_view()),
    path("api/private/v1/publication/decisions/", PublicationDecisionView.as_view()),
    path("api/private/v1/logbook/", LogbookOverviewView.as_view()),
    path("api/private/v1/logbook/export/", LogbookExportView.as_view()),
    path("api/private/v1/preview/events/", PreviewEventsView.as_view()),
    path("api/private/v1/preview/events/<uuid:id>/", PreviewEventView.as_view()),
    path("api/private/v1/preview/map-points/", PreviewMapView.as_view()),
    path("api/private/v1/preview/timeline/", PreviewTimelineView.as_view()),
    path("api/private/v1/sync/", SyncStatusView.as_view()),
    path(
        "api/v1/schema/",
        SpectacularAPIView.as_view(authentication_classes=[], permission_classes=[]),
    ),
    # Last: anything that is not the API, the admin or a static file is a page of the application.
    re_path(r"^(?!api(?:/|$)|admin(?:/|$)|static/|assets/).*$", frontend),
]
