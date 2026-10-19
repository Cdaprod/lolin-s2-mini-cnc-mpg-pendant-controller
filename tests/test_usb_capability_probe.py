"""Host-side regression tests for non-invasive CircuitPython probe."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "tools" / "probe_usb_capabilities.py"
spec = importlib.util.spec_from_file_location("usb_capability_probe", PATH)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

class FakeModule:
    safe_api = object()
    _private_api = object()

def test_import_is_not_enumeration():
    calls = []
    def importer(name):
        calls.append(name)
        if name == "usb_host":
            raise ImportError("not built")
        return FakeModule()
    result = probe.collect(importer)
    assert calls == list(probe.MODULES)
    assert result["host_verified"] is False
    assert result["ch34x_verified"] is False
    assert result["vbus_verified"] is False
    assert result["motion_enabled"] is False
    assert result["modules"][0]["available"] is False
    assert result["modules"][1]["exports"] == ["safe_api"]

def test_not_implemented_module():
    result = probe.inspect_module("usb_host", lambda _: (_ for _ in ()).throw(NotImplementedError()))
    assert result == {"module": "usb_host", "available": False, "error": "NotImplementedError"}
