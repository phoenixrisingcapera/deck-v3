"""Render-proof persistence contract; never fabricates browser output."""

from __future__ import annotations

from hashlib import sha256
import base64
import json
import os
import secrets
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path
from app.core.config import settings
from app.core.security import generate_id
from app.core.instant_html_crypto import get_instant_html_render_fernet
from app.services.rendering.playwright_render_child import (
    MAX_RENDER_DOCUMENT_BYTES,
    MAX_REQUEST_BYTES,
    serialize_request_payload,
)
from app.services.storage.artifact_storage import get_upload_storage

from sqlalchemy.orm import Session, object_session

from app.db.models import DesignVersion, InstantDeckCompilation, InstantDeckRenderProof
from app.services.rendering.html_deck_compiler import (
    AUTO_GRID_BODY_COMPILER_VERSION,
    AUTO_GRID_ITEM_COMPILER_VERSION,
    SVG_TEXT_GROUNDING_COMPILER_VERSION,
    RECT_GEOMETRY_COMPILER_VERSION,
    VIEWPORT_GEOMETRY_COMPILER_VERSION,
    INTENT_BOUND_COMPILER_VERSION,
    FACT_DIAGNOSTICS_COMPILER_VERSION,
    SVG_STYLES_COMPILER_VERSION,
    SVG_TEXT_LAYOUT_COMPILER_VERSION,
    OVERFLOW_SAFE_TEXT_COMPILER_VERSION,
    COMPILER_VERSION,
    PRESENTATION_PROOF_COMPILER_VERSION,
    READABLE_BODY_COMPILER_VERSION,
    VISUAL_SUBSTANCE_COMPILER_VERSION,
)


class RenderProofRequired(ValueError):
    pass


LEGACY_PRESENTATION_QUALITY_POLICY_VERSION = "presentation-scale.v1"
PRESENTATION_QUALITY_POLICY_VERSION = "presentation-scale.v2"
SUPPORTED_PRESENTATION_QUALITY_POLICY_VERSIONS = frozenset({
    LEGACY_PRESENTATION_QUALITY_POLICY_VERSION,
    PRESENTATION_QUALITY_POLICY_VERSION,
})
MAX_PRESENTATION_WORDS = 110
MIN_READABLE_TEXT_PX = 18.0
MIN_SUBSTANTIAL_BODY_PX = 24.0
MIN_MEDIAN_BODY_PX = 28.0
MIN_HEADING_PX = 56.0
MIN_FOCAL_TEXT_PX = 64.0
MIN_FOCAL_VISUAL_AREA_RATIO = 0.12
MIN_FOCAL_VISUAL_INK_AREA_RATIO = 0.04
MIN_STORY_VISUAL_AREA_RATIO = 0.08
MIN_STORY_VISUAL_INK_AREA_RATIO = 0.015


def chromium_subprocess_env() -> dict[str, str]:
    """Explicit Playwright-process allowlist; never inherit app credentials."""
    browser_path = "/ms-playwright"
    local_browser_path = str(os.getenv("INSTANT_HTML_LOCAL_PLAYWRIGHT_BROWSERS_PATH") or "").strip()
    local_executable_path = str(os.getenv("INSTANT_HTML_LOCAL_PLAYWRIGHT_EXECUTABLE_PATH") or "").strip()
    if local_browser_path:
        if str(os.getenv("RAILWAY_ENVIRONMENT") or "").strip():
            raise RenderProofRequired("Local Playwright browser overrides are forbidden in deployed environments.")
        candidate = Path(local_browser_path)
        if not candidate.is_absolute() or not candidate.is_dir():
            raise RenderProofRequired("Local Playwright browser path must be an existing absolute directory.")
        browser_path = str(candidate.resolve())
    child_env = {
        "HOME": "/tmp",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PLAYWRIGHT_BROWSERS_PATH": browser_path,
        "TMPDIR": "/tmp",
    }
    if local_executable_path:
        if not local_browser_path or str(os.getenv("RAILWAY_ENVIRONMENT") or "").strip():
            raise RenderProofRequired("Local Chromium executable overrides require an isolated local browser cache.")
        executable = Path(local_executable_path)
        cache_root = Path(browser_path)
        if (
            not executable.is_absolute()
            or not executable.is_file()
            or not os.access(executable, os.X_OK)
            or not executable.resolve().is_relative_to(cache_root.resolve())
        ):
            raise RenderProofRequired("Local Chromium executable must be runnable from the configured browser cache.")
        child_env["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"] = str(executable.resolve())
    return child_env


def read_encrypted_render_document(storage_key: str, expected_hash: str) -> str:
    path = get_upload_storage().resolve_path(storage_key)
    if path is None or not path.exists():
        raise RenderProofRequired("Sanitized render document is unavailable.")
    try:
        document = get_instant_html_render_fernet().decrypt(path.read_bytes()).decode("utf-8")
    except Exception as exc:
        raise RenderProofRequired("Sanitized render document could not be decrypted.") from exc
    if not secrets.compare_digest(sha256(document.encode()).hexdigest(), expected_hash):
        raise RenderProofRequired("Sanitized render document failed its integrity check.")
    return document


def viewport_hash(width: int, height: int, device_scale_factor: float = 1.0) -> str:
    return sha256(f"{width}x{height}@{device_scale_factor}".encode()).hexdigest()


def proof_hash(payload: dict) -> str:
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def presentation_quality_failure_codes(metrics: dict) -> list[str]:
    """Return content-free presentation-scale failures from real browser metrics."""
    quality = metrics.get("presentationQuality")
    if (
        not isinstance(quality, dict)
        or quality.get("policyVersion") not in SUPPORTED_PRESENTATION_QUALITY_POLICY_VERSIONS
    ):
        return ["presentation_quality_metrics_missing"]
    policy_version = str(quality["policyVersion"])
    failures: list[str] = []
    visible_words = quality.get("visibleWordCount")
    if not isinstance(visible_words, int) or isinstance(visible_words, bool):
        failures.append("presentation_word_count_missing")
    elif visible_words > MAX_PRESENTATION_WORDS:
        failures.append("presentation_word_count_exceeded")
    small_keys = quality.get("smallReadableTextKeys")
    if not isinstance(small_keys, list):
        failures.append("presentation_readability_metrics_missing")
    elif small_keys:
        failures.append("presentation_text_below_readable_floor")
    body_count = quality.get("substantialBodyCount")
    minimum_body = quality.get("minimumSubstantialBodyFontSize")
    median_body = quality.get("medianSubstantialBodyFontSize")
    if not isinstance(body_count, int) or isinstance(body_count, bool):
        failures.append("presentation_body_metrics_missing")
    elif body_count:
        if not isinstance(minimum_body, (int, float)) or isinstance(minimum_body, bool):
            failures.append("presentation_body_metrics_missing")
        elif float(minimum_body) < MIN_SUBSTANTIAL_BODY_PX:
            failures.append("presentation_body_below_readable_floor")
        if not isinstance(median_body, (int, float)) or isinstance(median_body, bool):
            failures.append("presentation_body_metrics_missing")
        elif float(median_body) < MIN_MEDIAN_BODY_PX:
            failures.append("presentation_body_scale_too_small")
    maximum_heading = quality.get("maximumHeadingFontSize")
    if not isinstance(maximum_heading, (int, float)) or isinstance(maximum_heading, bool):
        failures.append("presentation_heading_missing")
    elif float(maximum_heading) < MIN_HEADING_PX:
        failures.append("presentation_heading_scale_too_small")
    maximum_text = quality.get("maximumTextFontSize")
    visual_ratio = quality.get("largestVisualAreaRatio")
    visual_ink_ratio = quality.get("visualInkAreaRatio")
    if (
        not isinstance(maximum_text, (int, float))
        or isinstance(maximum_text, bool)
        or not isinstance(visual_ratio, (int, float))
        or isinstance(visual_ratio, bool)
        or (
            policy_version == PRESENTATION_QUALITY_POLICY_VERSION
            and (
                not isinstance(visual_ink_ratio, (int, float))
                or isinstance(visual_ink_ratio, bool)
            )
        )
    ):
        failures.append("presentation_focal_metrics_missing")
    elif (
        float(maximum_text) < MIN_FOCAL_TEXT_PX
        and (
            float(visual_ratio) < MIN_FOCAL_VISUAL_AREA_RATIO
            or (
                policy_version == PRESENTATION_QUALITY_POLICY_VERSION
                and float(visual_ink_ratio) < MIN_FOCAL_VISUAL_INK_AREA_RATIO
            )
        )
    ):
        failures.append("presentation_focal_scale_missing")
    return list(dict.fromkeys(failures))


def deck_presentation_quality_failure_codes(metrics_by_slide: list[dict], *, presentation_intent: str | None = None) -> list[str]:
    """Apply deck-wide background and visual-storytelling requirements."""
    if presentation_intent not in {None, "general", "investor_pitch"}:
        return ["presentation_intent_invalid"]
    if not metrics_by_slide:
        return ["presentation_deck_metrics_missing"]
    ratios: list[float] = []
    visual_slide_count = 0
    for metrics in metrics_by_slide:
        quality = metrics.get("presentationQuality") if isinstance(metrics, dict) else None
        policy_version = quality.get("policyVersion") if isinstance(quality, dict) else None
        ratio = quality.get("nearWhiteSampleRatio") if isinstance(quality, dict) else None
        if isinstance(ratio, (int, float)) and not isinstance(ratio, bool):
            ratios.append(float(ratio))
        visual_count = quality.get("visualElementCount") if isinstance(quality, dict) else None
        visual_ratio = quality.get("largestVisualAreaRatio") if isinstance(quality, dict) else None
        visual_ink_ratio = quality.get("visualInkAreaRatio") if isinstance(quality, dict) else None
        if (
            isinstance(visual_count, int)
            and not isinstance(visual_count, bool)
            and visual_count > 0
            and isinstance(visual_ratio, (int, float))
            and not isinstance(visual_ratio, bool)
            and float(visual_ratio) >= MIN_STORY_VISUAL_AREA_RATIO
            and (
                policy_version == LEGACY_PRESENTATION_QUALITY_POLICY_VERSION
                or (
                    policy_version == PRESENTATION_QUALITY_POLICY_VERSION
                    and isinstance(visual_ink_ratio, (int, float))
                    and not isinstance(visual_ink_ratio, bool)
                    and float(visual_ink_ratio) >= MIN_STORY_VISUAL_INK_AREA_RATIO
                )
            )
        ):
            visual_slide_count += 1
    if len(ratios) != len(metrics_by_slide):
        return ["presentation_background_metrics_missing"]
    failures: list[str] = []
    near_white_slides = sum(ratio >= 0.65 for ratio in ratios)
    allowed = max(1, len(metrics_by_slide) // 3)
    if presentation_intent != "general" and near_white_slides > allowed:
        failures.append("presentation_near_white_deck_exceeded")
    required_visual_slides = min(3, max(1, (len(metrics_by_slide) + 2) // 3))
    if visual_slide_count < required_visual_slides:
        failures.append("presentation_visual_storytelling_missing")
    return failures


def _compilation_presentation_intent(compilation: InstantDeckCompilation) -> str | None:
    # Historical proofs retain their original palette policy. New compilations
    # bind intent into their hash and manifest from trusted request context.
    if compilation.compiler_version not in {INTENT_BOUND_COMPILER_VERSION, FACT_DIAGNOSTICS_COMPILER_VERSION, SVG_STYLES_COMPILER_VERSION, SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION}:
        return None
    intent = (compilation.manifest_json or {}).get("presentationIntent")
    if intent not in {"general", "investor_pitch"}:
        raise RenderProofRequired("Canonical compilation presentation intent is missing.")
    return intent


def render_metrics_have_blocking_failure(
    metrics: dict,
    console_errors: list[str] | None = None,
    *,
    require_presentation_quality: bool = False,
    draft: bool = False,
) -> bool:
    if draft:
        # Layout/readability concerns remain recorded in metrics. A draft must
        # still render visibly in the same isolated browser with no errors.
        return bool(console_errors or not metrics.get('visible'))
    return bool(
        console_errors
        or not metrics.get("visible")
        or metrics.get("overflowX")
        or metrics.get("overflowY")
        or metrics.get("clippedElementKeys")
        or metrics.get("severeOverlapPairs")
        or (metrics.get("assetLoad") or {}).get("failedImageCount")
        or (metrics.get("accessibility") or {}).get("missingImageAlt")
        or (metrics.get("contrast") or {}).get("status") == "failed"
        or (require_presentation_quality and presentation_quality_failure_codes(metrics))
    )


def blocking_render_metric_summary(
    metrics: dict,
    console_errors: list[str] | None = None,
) -> dict[str, object]:
    """Return bounded, content-free evidence for a failed browser proof."""
    contrast_checks = (metrics.get("contrast") or {}).get("checks") or []
    quality = metrics.get("presentationQuality") if isinstance(metrics.get("presentationQuality"), dict) else {}
    return {
        "visible": bool(metrics.get("visible")),
        "overflowX": bool(metrics.get("overflowX")),
        "overflowY": bool(metrics.get("overflowY")),
        "clippedElementKeys": list(metrics.get("clippedElementKeys") or [])[:20],
        "severeOverlapPairs": list(metrics.get("severeOverlapPairs") or [])[:20],
        "failedImageCount": int((metrics.get("assetLoad") or {}).get("failedImageCount") or 0),
        "missingImageAlt": int((metrics.get("accessibility") or {}).get("missingImageAlt") or 0),
        "failedContrastKeys": [
            str(item.get("key") or "")
            for item in contrast_checks
            if isinstance(item, dict) and not item.get("passed")
        ][:20],
        "consoleErrorCount": len(console_errors or []),
        "presentationFailureCodes": presentation_quality_failure_codes(metrics),
        "visibleWordCount": quality.get("visibleWordCount"),
        "minimumSubstantialBodyFontSize": quality.get("minimumSubstantialBodyFontSize"),
        "medianSubstantialBodyFontSize": quality.get("medianSubstantialBodyFontSize"),
        "maximumHeadingFontSize": quality.get("maximumHeadingFontSize"),
        "maximumTextFontSize": quality.get("maximumTextFontSize"),
        "largestVisualAreaRatio": quality.get("largestVisualAreaRatio"),
        "visualInkAreaRatio": quality.get("visualInkAreaRatio"),
        "nearWhiteSampleRatio": quality.get("nearWhiteSampleRatio"),
    }


def require_complete_render_proofs(version: DesignVersion, db: Session | None = None) -> InstantDeckCompilation:
    db = db or object_session(version)
    if db is None:
        raise RenderProofRequired("HTML render proof validation requires a database session.")
    compilation = (
        db.query(InstantDeckCompilation)
        .filter(InstantDeckCompilation.design_version_id == version.id)
        .one_or_none()
    )
    if compilation is None or compilation.render_proof_status != "ready":
        raise RenderProofRequired("HTML compilation does not have complete real-browser render proof.")
    slides = list(version.generated_slides)
    proofs = (
        db.query(InstantDeckRenderProof)
        .filter(InstantDeckRenderProof.compilation_id == compilation.id)
        .all()
    )
    by_slide = {proof.generated_slide_id: proof for proof in proofs}
    if set(by_slide) != {slide.id for slide in slides}:
        raise RenderProofRequired("HTML render proof is incomplete for the compiled section set.")
    artifact_hash = str((compilation.manifest_json or {}).get("contentHash") or "")
    quality_policy_version = str(
        (compilation.manifest_json or {}).get("presentationQualityPolicyVersion") or ""
    )
    if (
        quality_policy_version
        and quality_policy_version not in SUPPORTED_PRESENTATION_QUALITY_POLICY_VERSIONS
    ):
        raise RenderProofRequired("HTML render proof uses an unsupported presentation-quality policy.")
    draft = (compilation.manifest_json or {}).get('evidencePolicy') == 'advisory-draft.v1'
    proof_metrics: list[dict] = []
    for slide in slides:
        proof = by_slide[slide.id]
        manifest_slide = next(
            (item for item in (compilation.manifest_json or {}).get("slides", []) if item.get("generatedSlideId") == slide.id),
            None,
        )
        if (
            manifest_slide is None
            or
            proof.status != "passed"
            or proof.artifact_hash != artifact_hash
            or proof.compilation_hash != compilation.content_hash
            or proof.sanitizer_policy_version != compilation.sanitizer_policy_version
            or proof.renderer_version != compilation.renderer_version
            or not proof.browser_version
            or not proof.viewport_hash
            or proof.render_document_hash != manifest_slide.get("renderDocumentHash")
            or not proof.screenshot_hash
        ):
            raise RenderProofRequired("HTML render proof identity does not match the canonical compilation.")
        if quality_policy_version and not draft:
            if presentation_quality_failure_codes(proof.metrics_json or {}):
                raise RenderProofRequired("HTML render proof does not satisfy presentation-scale quality.")
            proof_metrics.append(proof.metrics_json or {})
    if quality_policy_version and not draft and deck_presentation_quality_failure_codes(proof_metrics, presentation_intent=_compilation_presentation_intent(compilation)):
        raise RenderProofRequired("HTML render proof does not satisfy deck-wide presentation quality.")
    return compilation


class BrowserRendererAdapter:
    """Fetch/decrypt in parent; execute Playwright in a secret-free child."""

    _MAX_REQUEST_BYTES = MAX_REQUEST_BYTES
    _MAX_RENDER_DOCUMENT_BYTES = MAX_RENDER_DOCUMENT_BYTES
    _MAX_RESPONSE_BYTES = 20_000_000
    _MAX_STDERR_BYTES = 65_536
    _IO_CHUNK_BYTES = 65_536
    _REAP_TIMEOUT_SECONDS = 2.0

    @staticmethod
    def _close_process_pipes(process: subprocess.Popen) -> None:
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is None:
                continue
            try:
                pipe.close()
            except OSError:
                pass

    def _kill_and_reap(self, process: subprocess.Popen) -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            try:
                process.kill()
            except OSError:
                pass
        self._close_process_pipes(process)
        try:
            process.wait(timeout=self._REAP_TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass
            try:
                process.wait(timeout=self._REAP_TIMEOUT_SECONDS)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def _bounded_exchange(self, process: subprocess.Popen, request_bytes: bytes, *, timeout_seconds: int) -> bytes:
        if process.stdin is None or process.stdout is None or process.stderr is None:
            self._kill_and_reap(process)
            raise RenderProofRequired("Playwright child process pipes are unavailable.")
        selector = selectors.DefaultSelector()
        stdout = bytearray()
        stderr = bytearray()
        pending = memoryview(request_bytes)
        deadline = time.monotonic() + timeout_seconds
        try:
            for pipe in (process.stdin, process.stdout, process.stderr):
                os.set_blocking(pipe.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(cmd="playwright-render-child", timeout=timeout_seconds)
                events = selector.select(timeout=min(remaining, 0.1))
                for key, _mask in events:
                    pipe = key.fileobj
                    stream = key.data
                    if stream == "stdin":
                        try:
                            written = os.write(pipe.fileno(), pending[: self._IO_CHUNK_BYTES])
                            pending = pending[written:]
                        except (BrokenPipeError, OSError):
                            pending = pending[len(pending) :]
                        if not pending:
                            selector.unregister(pipe)
                            try:
                                pipe.close()
                            except OSError:
                                pass
                        continue
                    try:
                        chunk = os.read(pipe.fileno(), self._IO_CHUNK_BYTES)
                    except BlockingIOError:
                        continue
                    except OSError:
                        chunk = b""
                    if not chunk:
                        selector.unregister(pipe)
                        try:
                            pipe.close()
                        except OSError:
                            pass
                        continue
                    target = stdout if stream == "stdout" else stderr
                    target.extend(chunk)
                    ceiling = self._MAX_RESPONSE_BYTES if stream == "stdout" else self._MAX_STDERR_BYTES
                    if len(target) > ceiling:
                        raise RenderProofRequired(f"Playwright child {stream} exceeded its hard output ceiling.")
            remaining = max(0.01, deadline - time.monotonic())
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            self._kill_and_reap(process)
            raise RenderProofRequired("Playwright child process exceeded its render deadline.") from exc
        except Exception:
            self._kill_and_reap(process)
            raise
        finally:
            selector.close()
            self._close_process_pipes(process)
        if process.returncode != 0:
            raise RenderProofRequired("Playwright child process failed closed.")
        return bytes(stdout)

    def _run_child_payload(
        self,
        payload: dict,
        *,
        timeout_seconds: int,
        child_env: dict[str, str] | None = None,
        startup_grace_seconds: int = 0,
    ) -> dict:
        request_bytes = serialize_request_payload(payload)
        if len(request_bytes) > self._MAX_REQUEST_BYTES:
            raise RenderProofRequired("Playwright child-process request exceeds its bounded IPC limit.")
        child_script = Path(__file__).with_name("playwright_render_child.py").resolve()
        process = subprocess.Popen(
            [sys.executable, "-I", str(child_script)],
            cwd="/tmp",
            env=dict(child_env or chromium_subprocess_env()),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        stdout = self._bounded_exchange(
            process,
            request_bytes,
            timeout_seconds=timeout_seconds + max(0, startup_grace_seconds),
        )
        try:
            response = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RenderProofRequired("Playwright child process returned an invalid response.") from exc
        if not isinstance(response, dict):
            raise RenderProofRequired("Playwright child process returned an invalid response.")
        return response

    def _run_playwright_child(self, *, render_document: str, viewport: dict, timeout_seconds: int) -> dict:
        document_bytes = render_document.encode("utf-8")
        if len(document_bytes) > self._MAX_RENDER_DOCUMENT_BYTES:
            raise RenderProofRequired("Sanitized render document exceeds the child-process input limit.")
        response = self._run_child_payload(
            {
                "protocolVersion": 1,
                "operation": "render",
                # Fixed base64 expansion prevents adversarial HTML control
                # characters from multiplying unpredictably under JSON string
                # escaping while preserving the exact UTF-8 document bytes.
                "renderDocumentBase64": base64.b64encode(document_bytes).decode("ascii"),
                "viewport": {
                    "width": int(viewport["width"]),
                    "height": int(viewport["height"]),
                    "deviceScaleFactor": float(viewport.get("deviceScaleFactor", 1)),
                },
                "timeoutSeconds": timeout_seconds,
            },
            timeout_seconds=timeout_seconds,
            startup_grace_seconds=5,
        )
        try:
            screenshot = base64.b64decode(response["screenshotBase64"], validate=True)
        except (KeyError, TypeError, ValueError) as exc:
            raise RenderProofRequired("Playwright child process returned an invalid response.") from exc
        if (
            response.get("ok") is not True
            or not isinstance(response.get("browserVersion"), str)
            or not isinstance(response.get("metrics"), dict)
            or not isinstance(response.get("consoleErrors"), list)
            or len(screenshot) > self._MAX_RESPONSE_BYTES
        ):
            raise RenderProofRequired("Playwright child process returned an invalid response.")
        return {**response, "screenshot": screenshot}

    def render(
        self,
        *,
        render_document: str,
        viewport: dict,
        quality_policy_version: str | None = None,
        draft: bool = False,
    ) -> dict:
        role = (os.getenv("WORKER_KIND") or os.getenv("APP_ROLE") or "").strip().lower().replace("-", "_")
        if role not in {"preview_render", "worker_preview_render"}:
            raise RenderProofRequired("Chromium render proof may run only in the dedicated preview-render worker role.")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            raise RenderProofRequired("Chromium render proof refuses to run as root.")
        # Re-evaluate the parent process immediately before importing/spawning
        # Playwright. Settings imports may have happened earlier in worker
        # startup, so this boundary must independently fail closed.
        from app.workers.render_role_security import validate_render_worker_secret_contract

        try:
            validate_render_worker_secret_contract()
        except RuntimeError as exc:
            raise RenderProofRequired("Preview renderer process credential isolation failed.") from exc
        try:
            timeout_seconds = max(1, min(
                settings.instant_html_max_wall_seconds,
                int(viewport.get("timeoutSeconds", settings.instant_html_max_wall_seconds)),
            ))
            child_result = self._run_playwright_child(
                render_document=render_document,
                viewport=viewport,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            if isinstance(exc, RenderProofRequired):
                raise
            raise RenderProofRequired("Real Chromium render proof failed closed.") from exc
        metrics = child_result["metrics"]
        console_errors = child_result["consoleErrors"]
        require_presentation_quality = quality_policy_version == PRESENTATION_QUALITY_POLICY_VERSION
        if quality_policy_version not in {None, "", PRESENTATION_QUALITY_POLICY_VERSION}:
            raise RenderProofRequired("Unsupported presentation-quality policy.")
        if render_metrics_have_blocking_failure(
            metrics,
            console_errors,
            require_presentation_quality=require_presentation_quality, draft=draft,
        ):
            summary = json.dumps(
                blocking_render_metric_summary(metrics, console_errors),
                sort_keys=True,
                separators=(",", ":"),
            )
            raise RenderProofRequired(
                f"Compiled slide failed browser visibility/overflow validation: {summary}"
            )
        return {
            "browserVersion": child_result["browserVersion"],
            "metrics": metrics,
            "consoleErrorCount": len(console_errors),
            "screenshotHash": sha256(child_result["screenshot"]).hexdigest(),
            "screenshot": child_result["screenshot"],
        }


def create_complete_render_proofs(db: Session, version: DesignVersion, *, adapter: BrowserRendererAdapter | None = None) -> InstantDeckCompilation:
    """Render every exact sanitized section and atomically mark proof ready."""
    if not settings.instant_html_enabled:
        raise RenderProofRequired("Full HTML Instant Deck rendering is disabled by configuration.")
    compilation = db.query(InstantDeckCompilation).filter(InstantDeckCompilation.design_version_id == version.id).one_or_none()
    if compilation is None:
        raise RenderProofRequired("HTML compilation is missing.")
    if compilation.render_proof_status == "ready":
        return require_complete_render_proofs(version, db)
    quality_policy_version = (
        PRESENTATION_QUALITY_POLICY_VERSION
        if compilation.compiler_version in {
            VISUAL_SUBSTANCE_COMPILER_VERSION,
            PRESENTATION_PROOF_COMPILER_VERSION,
            READABLE_BODY_COMPILER_VERSION,
            AUTO_GRID_BODY_COMPILER_VERSION,
            AUTO_GRID_ITEM_COMPILER_VERSION,
            SVG_TEXT_GROUNDING_COMPILER_VERSION,
            RECT_GEOMETRY_COMPILER_VERSION,
            VIEWPORT_GEOMETRY_COMPILER_VERSION,
            INTENT_BOUND_COMPILER_VERSION,
            FACT_DIAGNOSTICS_COMPILER_VERSION,
            SVG_STYLES_COMPILER_VERSION,
            OVERFLOW_SAFE_TEXT_COMPILER_VERSION,
            SVG_TEXT_LAYOUT_COMPILER_VERSION, COMPILER_VERSION,
        }
        else None
    )
    draft = (compilation.manifest_json or {}).get('evidencePolicy') == 'advisory-draft.v1'
    viewport = {"width": 1920, "height": 1080, "deviceScaleFactor": 1}
    adapter = adapter or BrowserRendererAdapter()
    artifact_hash = str((compilation.manifest_json or {}).get("contentHash") or "")
    slides = sorted(version.generated_slides, key=lambda item: item.slide_number)
    if not slides:
        raise RenderProofRequired("HTML compilation contains no sections.")
    started = time.monotonic()
    rendered_metrics: list[dict] = []
    rendered_slides: list[dict] = []
    for slide in slides:
        if time.monotonic() - started >= settings.instant_html_max_wall_seconds:
            raise RenderProofRequired("Aggregate render-proof deadline exceeded.")
        manifest_slide = next(
            (item for item in (compilation.manifest_json or {}).get("slides", []) if item.get("generatedSlideId") == slide.id),
            None,
        )
        if manifest_slide is None:
            raise RenderProofRequired("A sanitized slide render document identity is missing.")
        document_hash = str(manifest_slide.get("renderDocumentHash") or "")
        document = read_encrypted_render_document(str(manifest_slide.get("renderDocumentStorageKey") or ""), document_hash)
        rendered = adapter.render(
            render_document=document,
            viewport={
                **viewport,
                "timeoutSeconds": max(1, int(settings.instant_html_max_wall_seconds - (time.monotonic() - started))),
            },
            quality_policy_version=quality_policy_version,
            **({"draft": True} if draft else {}),
        )
        rendered_metrics.append(rendered["metrics"])
        if isinstance(rendered.get("screenshot"), bytes):
            rendered_slides.append({
                "slideId": slide.id,
                "screenshot": rendered["screenshot"],
                "metrics": rendered["metrics"],
            })
        identity = {
            "artifactHash": artifact_hash,
            "compilationHash": compilation.content_hash,
            "sanitizerPolicyVersion": compilation.sanitizer_policy_version,
            "rendererVersion": compilation.renderer_version,
            "browserVersion": rendered["browserVersion"],
            "viewportHash": viewport_hash(1920, 1080),
            "generatedSlideId": slide.id,
            "renderDocumentHash": document_hash,
            "screenshotHash": rendered["screenshotHash"],
            "metrics": rendered["metrics"],
            "presentationQualityPolicyVersion": quality_policy_version,
        }
        db.add(InstantDeckRenderProof(
            id=generate_id("renderproof"), compilation_id=compilation.id, generated_slide_id=slide.id,
            artifact_hash=artifact_hash, compilation_hash=compilation.content_hash,
            render_document_hash=document_hash, screenshot_hash=rendered["screenshotHash"],
            sanitizer_policy_version=compilation.sanitizer_policy_version, renderer_version=compilation.renderer_version,
            browser_version=rendered["browserVersion"], viewport_hash=identity["viewportHash"],
            proof_hash=proof_hash(identity), status="passed", metrics_json=rendered["metrics"],
        ))
    if quality_policy_version and not draft:
        deck_failures = deck_presentation_quality_failure_codes(rendered_metrics, presentation_intent=_compilation_presentation_intent(compilation))
        if deck_failures:
            raise RenderProofRequired(
                "Compiled deck failed presentation-quality validation: "
                + json.dumps({"presentationFailureCodes": deck_failures}, separators=(",", ":"))
            )
    compilation.render_proof_status = "ready"
    compilation.stage = "render_proof_ready"
    manifest = dict(compilation.manifest_json or {})
    manifest["renderProofStatus"] = "ready"
    if draft:
        manifest["draftLayoutWarnings"] = [{"slide": i, **blocking_render_metric_summary(m)} for i, m in enumerate(rendered_metrics, 1) if render_metrics_have_blocking_failure(m, require_presentation_quality=True)]
    if quality_policy_version:
        manifest["presentationQualityPolicyVersion"] = quality_policy_version
    compilation.manifest_json = manifest
    generation_result = (
        version.generation_job.result_json
        if version.generation_job is not None and isinstance(version.generation_job.result_json, dict)
        else {}
    )
    operation_id = str(generation_result.get("operationId") or version.generation_job_id or version.id)
    if rendered_slides:
        try:
            from app.services.visual_intelligence.review import persist_rendered_deck_review
            with db.begin_nested():
                review = persist_rendered_deck_review(
                    db, deck_id=version.deck_id, operation_id=operation_id, rendered_slides=rendered_slides,
                )
            manifest = dict(compilation.manifest_json or {})
            manifest["visionReviewStatus"] = "ready" if review else "not_requested"
            compilation.manifest_json = manifest
        except Exception:
            # Visual critique is advisory. Never turn storage/review failure into
            # a publication or export failure after canonical render proof passes.
            manifest = dict(compilation.manifest_json or {})
            manifest["visionReviewStatus"] = "unavailable"
            compilation.manifest_json = manifest
    db.commit()
    if rendered_slides:
        try:
            from app.services.visual_intelligence.review.deck_review import (
                enhance_rendered_deck_review_with_llm,
            )

            enhanced_review = enhance_rendered_deck_review_with_llm(
                db,
                deck_id=version.deck_id,
                operation_id=operation_id,
                rendered_slides=rendered_slides,
            )
            manifest = dict(compilation.manifest_json or {})
            manifest["investorHandoffReviewStatus"] = (
                "ready"
                if isinstance(enhanced_review, dict)
                and enhanced_review.get("review_source") == "llm_assisted"
                else "not_requested"
            )
            compilation.manifest_json = manifest
            db.commit()
        except Exception:
            # Investor-quality judgment is internal advice. Provider, budget,
            # or parsing failures must not invalidate a factually and
            # technically valid export.
            manifest = dict(compilation.manifest_json or {})
            manifest["investorHandoffReviewStatus"] = "unavailable"
            compilation.manifest_json = manifest
            db.commit()
    return require_complete_render_proofs(version, db)
