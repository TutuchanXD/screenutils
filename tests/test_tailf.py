import pytest

from screenctl.screen import Screen, tailf


SCREEN_LS = """There is a screen on:
\t1234.job\t(Detached)
1 Socket in /run/screen/S-user.
"""


def test_tailf_yields_appended_text_without_busy_wait(monkeypatch, tmp_path):
    sleeps = []
    monkeypatch.setattr("screenctl.screen.sleep", lambda seconds: sleeps.append(seconds))

    log_file = tmp_path / "screen.log"
    log_file.write_text("initial")

    logs = tailf(log_file, interval=0.25)

    assert next(logs) == ""
    assert sleeps == [0.25]

    log_file.write_text("initial\nnext")

    assert next(logs) == "\nnext"


def test_tailf_reads_from_start_after_truncation(tmp_path):
    log_file = tmp_path / "screen.log"
    log_file.write_text("initial content")

    logs = tailf(log_file, interval=0)

    assert next(logs) == ""

    log_file.write_text("new")

    assert next(logs) == "new"


def test_tailf_missing_initial_file_raises_by_default(tmp_path):
    log_file = tmp_path / "missing.log"

    with pytest.raises(FileNotFoundError):
        next(tailf(log_file))


def test_tailf_can_wait_for_missing_file(monkeypatch, tmp_path):
    sleeps = []
    monkeypatch.setattr("screenctl.screen.sleep", lambda seconds: sleeps.append(seconds))

    log_file = tmp_path / "missing.log"
    logs = tailf(log_file, interval=0.5, missing_ok=True)

    assert next(logs) == ""
    assert sleeps == [0.5]

    log_file.write_text("created")

    assert next(logs) == "created"


def test_tailf_replaces_invalid_bytes_when_configured(tmp_path):
    log_file = tmp_path / "screen.log"
    log_file.write_bytes(b"initial")

    logs = tailf(log_file, interval=0, encoding="utf-8", errors="replace")

    assert next(logs) == ""

    log_file.write_bytes(b"initial\xff")

    assert next(logs) == "\ufffd"


def test_tail_logs_requires_logs_to_be_enabled():
    screen = Screen("job")

    with pytest.raises(RuntimeError, match="Logs are not enabled"):
        next(screen.tail_logs())


def test_enable_logs_configures_tail_logs(monkeypatch, tmp_path):
    log_file = tmp_path / "screen.log"

    monkeypatch.setattr("screenctl.screen._screen_output", lambda *args: SCREEN_LS)
    monkeypatch.setattr("screenctl.screen._run_screen", lambda *args: None)
    monkeypatch.setattr("screenctl.screen.sleep", lambda seconds: None)

    screen = Screen("job")
    screen.enable_logs(str(log_file), interval=0)

    assert next(screen.logs) == ""

    log_file.write_text("hello")

    assert next(screen.logs) == "hello"


def test_tail_logs_stops_after_timeout(monkeypatch, tmp_path):
    times = iter([0.0, 0.05, 0.2])
    monkeypatch.setattr("screenctl.screen.monotonic", lambda: next(times))
    monkeypatch.setattr("screenctl.screen.sleep", lambda seconds: None)

    log_file = tmp_path / "screen.log"
    log_file.write_text("")

    screen = Screen("job")
    screen._logfilename = str(log_file)

    logs = screen.tail_logs(timeout=0.1, interval=0)

    assert next(logs) == ""
    with pytest.raises(StopIteration):
        next(logs)
