import pytest
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.tools.builtin.open_app import open_app
from voicecore.tools.registry import ToolRegistry


@pytest.mark.real_model
def test_needle_router_with_real_model():
    registry = ToolRegistry()
    registry.register(open_app, tier="T1", name="open_app")

    with NeedleRouter(registry=registry, stateless=True) as router:
        res = router.route("open notepad")
        assert len(res.calls) == 1
        assert res.calls[0].name == "open_app"
        assert res.calls[0].arguments.get("app_name", "").lower() == "notepad"
        assert res.confidence > 0.70
        assert res.negation is False
        assert res.ungrounded == []
