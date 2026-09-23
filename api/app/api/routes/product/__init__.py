from __future__ import annotations

from fastapi import APIRouter
from fastapi.routing import APIRoute

from app.api.routes.brand_extraction import router as brand_extraction_router
from app.api.routes.deck_artifacts import router as deck_artifacts_router
from app.api.routes.deck_identity import router as deck_identity_router
from app.api.routes.deck_retry_rescue import router as deck_retry_rescue_router
from app.api.routes.deck_workflow import router as deck_workflow_router
from app.api.routes.decks import router as decks_router
from app.api.routes.instant_deck import router as instant_deck_router
from app.api.routes.product_intake_cleanup import router as product_intake_cleanup_router
from app.api.routes.product_processing import router as product_processing_router
from app.api.routes.product_upload_compat import router as product_upload_compat_router
from app.api.routes.products import router as products_router
from app.api.routes.upload_rescue import router as upload_rescue_router
from app.api.routes.workspace_dashboard import router as workspace_dashboard_router

# Product routers serve the reduced customer workflow. Mixed legacy modules
# remain only while they still own a required upload, processing, workflow, or
# dashboard endpoint; pure excluded routers are intentionally not registered.


def _route_subset(source: APIRouter, *, paths: set[str]) -> APIRouter:
    """Mount canonical handlers only for explicitly retained product paths."""
    selected = [
        route
        for route in source.routes
        if isinstance(route, APIRoute) and route.path in paths
    ]
    missing = paths.difference(route.path for route in selected)
    if missing:
        raise RuntimeError(f"Required product routes are unavailable: {sorted(missing)}")
    return APIRouter(routes=selected)


deck_artifacts_runtime_router = _route_subset(
    deck_artifacts_router,
    paths={
        "/products/deck-aistack-codes/decks/{deck_id}/html-artifacts/{artifact_id}/slides/{generated_slide_id}/capability",
    },
)
deck_workflow_runtime_router = _route_subset(
    deck_workflow_router,
    paths={
        "/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
        "/products/deck-aistack-codes/decks/{deck_id}/workflows/source-extraction",
        "/products/deck-aistack-codes/decks/{deck_id}/workflows/brand-extraction",
        "/products/deck-aistack-codes/decks/{deck_id}/workflows/smart-deck-generation",
        "/products/deck-aistack-codes/decks/{deck_id}/workflows/smart-deck-generation/retry-failed",
        "/products/deck-aistack-codes/decks/{deck_id}/workflows/export",
        "/products/deck-aistack-codes/decks/{deck_id}/exports",
        "/products/deck-aistack-codes/decks/{deck_id}/exports/{export_id}",
        "/products/deck-aistack-codes/decks/{deck_id}/exports/{export_id}/download",
        "/workflow-jobs/{job_id}",
    },
)
brand_extraction_runtime_router = _route_subset(
    brand_extraction_router,
    paths={
        "/products/deck-aistack-codes/decks/{deck_id}/brand-assets/{asset_id}",
        "/products/deck-aistack-codes/decks/{deck_id}/brand-profile",
    },
)
decks_runtime_router = _route_subset(
    decks_router,
    paths={
        "/decks",
        "/decks/{deck_id}",
        "/decks/{deck_id}/upload-url",
        "/decks/{deck_id}/upload-complete",
    },
)
products_runtime_router = _route_subset(
    products_router,
    paths={
        "/products/deck-aistack-codes/welcome-state",
        "/products/deck-aistack-codes/workspace-summary",
        "/products/deck-aistack-codes/decks",
        "/products/deck-aistack-codes/decks/first-batch",
        "/products/deck-aistack-codes/decks/upload-session",
        "/products/deck-aistack-codes/decks/upload-completion",
        "/products/deck-aistack-codes/decks/{deck_id}/soft-delete",
    },
)
workspace_dashboard_runtime_router = _route_subset(
    workspace_dashboard_router,
    paths={"/workspace/dashboard"},
)


PRODUCT_ROUTERS: tuple[tuple[APIRouter, str], ...] = (
    (upload_rescue_router, "/api"),
    (product_upload_compat_router, "/api"),
    (deck_retry_rescue_router, "/api"),
    (brand_extraction_runtime_router, "/api"),
    (deck_artifacts_runtime_router, "/api"),
    (deck_identity_router, "/api"),
    (product_intake_cleanup_router, "/api"),
    (product_processing_router, "/api"),
    (products_runtime_router, "/api"),
    (deck_workflow_runtime_router, "/api"),
    (instant_deck_router, "/api"),
    (decks_runtime_router, "/api"),
    (workspace_dashboard_runtime_router, "/api"),
)
