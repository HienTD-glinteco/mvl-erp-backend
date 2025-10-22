from types import SimpleNamespace

from libs.drf.spectacular.ordering import AutoDocOrderingFilterExtension


def test_extension_returns_empty_when_no_fields():
    schema = SimpleNamespace(view=SimpleNamespace(ordering_fields=None, ordering=None))
    assert AutoDocOrderingFilterExtension().get_schema_operation_parameters(schema) == []


def test_extension_generates_description():
    view = SimpleNamespace(ordering_fields=["id", "name"], ordering=["-name"])
    schema = SimpleNamespace(view=view)
    params = AutoDocOrderingFilterExtension().get_schema_operation_parameters(schema)
    assert params[0]["name"] == "ordering"
    assert "`id`, `name`" in params[0]["description"]
    assert "`-name`" in params[0]["description"]
