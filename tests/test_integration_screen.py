import shutil
import time
from uuid import uuid4

import pytest

from screenutils import Screen, list_screens


pytestmark = pytest.mark.integration


def _screen_available():
    return shutil.which("screen") is not None


@pytest.fixture
def screen_session():
    if not _screen_available():
        pytest.skip("GNU screen binary is not installed")

    name = f"screenutils-it-{uuid4().hex}"
    screen = Screen.create(name)
    try:
        yield screen
    finally:
        try:
            if screen.exists:
                screen.quit()
        except Exception:
            pass


def _wait_for(predicate, timeout=3.0, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return predicate()


def test_screen_lifecycle_against_real_gnu_screen(screen_session):
    assert screen_session.exists is True
    assert any(screen.name == screen_session.name for screen in list_screens())

    screen_session.quit()

    assert _wait_for(lambda: not screen_session.exists) is True


def test_send_text_and_send_line_against_real_gnu_screen(screen_session):
    typed = "screenutils-integration-ok"

    screen_session.send_text(typed)

    def hardcopy_contains_typed_text():
        return typed in screen_session.hardcopy()

    assert _wait_for(hardcopy_contains_typed_text, timeout=5.0) is True

    screen_session.send_line("clear")
