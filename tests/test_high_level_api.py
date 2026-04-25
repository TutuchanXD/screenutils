import pytest

from screenutils import Screen
from screenutils.errors import ScreenNotFoundError


SCREEN_LS = """There is a screen on:
\t1234.job\t(Detached)
1 Socket in /run/screen/S-user.
"""

NO_SCREENS = """No Sockets found in /run/screen/S-user.
"""


def test_create_initializes_and_returns_screen(monkeypatch):
    calls = []
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: NO_SCREENS)
    monkeypatch.setattr("screenutils.screen._run_screen", lambda *args: calls.append(args))

    screen = Screen.create("job")

    assert isinstance(screen, Screen)
    assert screen.name == "job"
    assert calls == [("-dmS", "job")]


def test_ensure_is_create_alias(monkeypatch):
    calls = []
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: NO_SCREENS)
    monkeypatch.setattr("screenutils.screen._run_screen", lambda *args: calls.append(args))

    screen = Screen.ensure("job")

    assert isinstance(screen, Screen)
    assert calls == [("-dmS", "job")]


def test_get_returns_existing_screen(monkeypatch):
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: SCREEN_LS)

    screen = Screen.get("job")

    assert screen.name == "job"
    assert screen.exists is True


def test_get_raises_for_missing_screen(monkeypatch):
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: NO_SCREENS)

    with pytest.raises(ScreenNotFoundError):
        Screen.get("job")


def test_send_text_sends_without_enter(monkeypatch):
    calls = []
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: SCREEN_LS)
    monkeypatch.setattr("screenutils.screen._run_screen", lambda *args: calls.append(args))
    monkeypatch.setattr("screenutils.screen.sleep", lambda seconds: None)

    Screen("job").send_text("hello")

    assert calls == [("-S", "1234", "-X", "stuff", "hello")]


def test_send_line_sends_text_and_enter(monkeypatch):
    calls = []
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: SCREEN_LS)
    monkeypatch.setattr("screenutils.screen._run_screen", lambda *args: calls.append(args))
    monkeypatch.setattr("screenutils.screen.sleep", lambda seconds: None)

    Screen("job").send_line("echo hello")

    assert calls == [("-S", "1234", "-X", "stuff", "echo hello\n")]


def test_legacy_send_commands_delegates_to_send_line(monkeypatch):
    calls = []
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: SCREEN_LS)
    monkeypatch.setattr("screenutils.screen._run_screen", lambda *args: calls.append(args))
    monkeypatch.setattr("screenutils.screen.sleep", lambda seconds: None)

    Screen("job").send_commands("one", "two")

    assert calls == [
        ("-S", "1234", "-X", "stuff", "one\n"),
        ("-S", "1234", "-X", "stuff", "two\n"),
    ]


def test_ctrl_c_and_quit_aliases(monkeypatch):
    calls = []
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: SCREEN_LS)
    monkeypatch.setattr("screenutils.screen._run_screen", lambda *args: calls.append(args))
    monkeypatch.setattr("screenutils.screen.sleep", lambda seconds: None)

    screen = Screen("job")
    screen.ctrl_c()
    screen.quit()

    assert calls == [
        ("-x", "1234", "-X", 'eval "stuff \\003"'),
        ("-x", "1234", "-X", "quit"),
    ]
