from subprocess import CalledProcessError
from unittest.mock import Mock

import pytest

from screenutils.screen import Screen, _run_screen, _screen_output


SCREEN_LS = """There is a screen on:
	1234.job	(Detached)
1 Socket in /run/screen/S-user.
"""


def test_run_screen_uses_argument_list_without_shell(monkeypatch):
    run_mock = Mock()
    monkeypatch.setattr("screenutils.screen.run", run_mock)

    _run_screen("-d", "1234")

    run_mock.assert_called_once()
    args, kwargs = run_mock.call_args
    assert args[0] == ["screen", "-d", "1234"]
    assert "shell" not in kwargs
    assert kwargs["check"] is True


def test_screen_output_returns_output_from_non_zero_screen_command(monkeypatch):
    def fake_run(*args, **kwargs):
        raise CalledProcessError(1, args[0], output="No Sockets found.\n")

    monkeypatch.setattr("screenutils.screen.run", fake_run)

    assert _screen_output("-ls") == "No Sockets found.\n"


def test_initialize_creates_detached_session_without_tty(monkeypatch):
    calls = []
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: "No Sockets found.\n")
    monkeypatch.setattr("screenutils.screen._run_screen", lambda *args: calls.append(args))

    Screen("job; rm -rf /", initialize=True)

    assert calls == [("-dmS", "job; rm -rf /")]


def test_initialize_does_not_create_existing_session(monkeypatch):
    calls = []
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: SCREEN_LS)
    monkeypatch.setattr("screenutils.screen._run_screen", lambda *args: calls.append(args))

    Screen("job", initialize=True)

    assert calls == []


def test_detach_runs_screen_d_with_cached_screen_id(monkeypatch):
    calls = []
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: SCREEN_LS)
    monkeypatch.setattr("screenutils.screen._run_screen", lambda *args: calls.append(args))

    Screen("job").detach()

    assert calls == [("-d", "1234")]


def test_screen_commands_run_through_argument_list(monkeypatch):
    calls = []
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: SCREEN_LS)
    monkeypatch.setattr("screenutils.screen._run_screen", lambda *args: calls.append(args))
    monkeypatch.setattr("screenutils.screen.sleep", lambda seconds: None)

    Screen("job")._screen_commands("quit")

    assert calls == [("-x", "1234", "-X", "quit")]


def test_disable_logs_removes_log_file_with_pathlib(monkeypatch, tmp_path):
    log_file = tmp_path / "screen.log"
    log_file.write_text("hello")

    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: SCREEN_LS)
    monkeypatch.setattr("screenutils.screen._run_screen", lambda *args: None)
    monkeypatch.setattr("screenutils.screen.sleep", lambda seconds: None)

    screen = Screen("job")
    screen._logfilename = str(log_file)
    screen.disable_logs(remove_logfile=True)

    assert not log_file.exists()


def test_disable_logs_does_not_remove_log_file_by_default(monkeypatch, tmp_path):
    log_file = tmp_path / "screen.log"
    log_file.write_text("hello")

    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: SCREEN_LS)
    monkeypatch.setattr("screenutils.screen._run_screen", lambda *args: None)
    monkeypatch.setattr("screenutils.screen.sleep", lambda seconds: None)

    screen = Screen("job")
    screen._logfilename = str(log_file)
    screen.disable_logs()

    assert log_file.exists()
