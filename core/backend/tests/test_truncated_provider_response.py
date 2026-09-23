"""A truncated successful response may be retrieved once, never regenerated."""
import json
from http.client import IncompleteRead

import pytest

from app.services.llm import openai_provider as provider


def test_truncated_response_retrieval_is_bounded_and_preserves_usage(monkeypatch):
    class Response:
        status = 200
        headers = {"x-request-id": "req-original"}
        def __init__(self, body):
            self.body = body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            if isinstance(self.body, Exception):
                raise self.body
            return json.dumps(self.body).encode()

    payload = {"id": "resp_same", "model": "gpt-5-2025-08-07", "status": "completed",
               "output": [], "usage": {"input_tokens": 62144, "output_tokens": 17850}}
    call = provider.call_openai_response.__wrapped__
    for scenario in ("success", "missing-id", "expired", "get-failed", "mismatched"):
        calls = []
        clock = iter([100.0, 221.0 if scenario == "expired" else 110.0, 111.0])
        monkeypatch.setattr(provider.time, "monotonic", lambda: next(clock))
        def transport(request, timeout):
            calls.append((request.get_method(), request.full_url, timeout))
            if request.get_method() == "POST":
                prefix = b'{"id":"resp_same", "output":[' if scenario != "missing-id" else b'{"output":['
                return Response(IncompleteRead(prefix, 55834))
            assert request.data is None and len(calls) == 2
            if scenario == "get-failed":
                return Response(IncompleteRead(b'{"id":"resp_same"', 100))
            return Response({**payload, "id": "resp_other"} if scenario == "mismatched" else payload)
        monkeypatch.setattr(provider.url_request, "urlopen", transport)
        kwargs = dict(api_key="test-placeholder", model=payload["model"], system="General presentation", user="Synthetic source",
                      timeout=120, timeout_ceiling=120, recover_truncated_response=True, client_request_id="client-one")
        if scenario == "success":
            result = call(**kwargs)
            assert result["usage"] == payload["usage"]
            assert result["_transport_metadata"]["provider_request_id"] == "req-original"
            assert result["_transport_metadata"]["response_retrieval_count"] == 1
        else:
            with pytest.raises(provider.OpenAITransportError) as error:
                call(**kwargs)
            assert not provider._is_retryable_openai_error(error.value)
            assert "test-placeholder" not in str(error.value)
        assert [c[0] for c in calls].count("POST") == 1
        assert len(calls) == (1 if scenario in {"missing-id", "expired"} else 2)
        if len(calls) == 2:
            assert calls[1][1] == provider.OPENAI_RESPONSES_URL + "/resp_same"
            assert 0 < calls[1][2] <= 30
