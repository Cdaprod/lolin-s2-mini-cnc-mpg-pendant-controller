import contextlib
import io

from src.diagnostics import emit


def test_structured_diagnostic_line_has_bounded_single_token_fields():
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        emit("touch gesture", kind="swipe left", x=12, error=None)
    assert output.getvalue().strip() == (
        "[event] event=touch_gesture kind=swipe_left x=12")
