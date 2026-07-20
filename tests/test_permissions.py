from qnexus_mcp.config import ServerConfig
from qnexus_mcp.permissions import ToolSpec, annotations_for, is_tool_allowed, select_tools


def _spec(**kw):
    return ToolSpec(
        name=kw.pop("name", "t"),
        toolset=kw.pop("toolset", "read"),
        handler=lambda **_: None,
        **kw,
    )


def test_read_tool_allowed_by_default():
    assert is_tool_allowed(_spec(toolset="read", read_only=True), ServerConfig())


def test_execute_tool_hidden_unless_toolset_enabled():
    spec = _spec(name="submit", toolset="execute", is_spend=True)
    assert not is_tool_allowed(spec, ServerConfig())
    assert is_tool_allowed(spec, ServerConfig(toolsets=frozenset({"read", "execute"})))


def test_destructive_needs_flag_even_with_toolset():
    spec = _spec(toolset="destructive", is_destructive=True)
    cfg = ServerConfig(toolsets=frozenset({"read", "destructive"}))
    assert not is_tool_allowed(spec, cfg)
    assert is_tool_allowed(spec, cfg.model_copy(update={"allow_destructive": True}))


def test_select_tools_filters_the_exposed_list():
    specs = [
        _spec(name="r", toolset="read", read_only=True),
        _spec(name="x", toolset="execute", is_spend=True),
    ]
    names = [s.name for s in select_tools(specs, ServerConfig())]
    assert names == ["r"]  # register-time omission: execute tool never appears


def test_annotations_mapping():
    a = annotations_for(_spec(read_only=True, idempotent=True))
    assert a == {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
