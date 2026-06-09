import pytest

from article_api.route_error_handlers import call_with_http_error


def test_call_with_http_error_returns_action_result():
    calls = []

    result = call_with_http_error(lambda: calls.append("action") or {"status": "ok"}, lambda exc: calls.append(exc))

    assert result == {"status": "ok"}
    assert calls == ["action"]


def test_call_with_http_error_maps_then_reraises_original_when_mapper_returns():
    calls = []
    error = RuntimeError("broken")

    def action():
        raise error

    with pytest.raises(RuntimeError) as exc_info:
        call_with_http_error(action, lambda exc: calls.append(exc))

    assert exc_info.value is error
    assert calls == [error]


def test_call_with_http_error_allows_mapper_to_raise_http_exception():
    original = LookupError("missing")
    mapped = ValueError("http")

    def action():
        raise original

    def raise_http_error(exc):
        assert exc is original
        raise mapped

    with pytest.raises(ValueError) as exc_info:
        call_with_http_error(action, raise_http_error)

    assert exc_info.value is mapped
