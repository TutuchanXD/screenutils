from screenutils.screen import tailf


def test_tailf_yields_appended_text_without_busy_wait(monkeypatch, tmp_path):
    sleeps = []
    monkeypatch.setattr("screenutils.screen.sleep", lambda seconds: sleeps.append(seconds))

    log_file = tmp_path / "screen.log"
    log_file.write_text("initial")

    logs = tailf(log_file, interval=0.25)

    assert next(logs) == ""
    assert sleeps == [0.25]

    log_file.write_text("initial\nnext")

    assert next(logs) == "\nnext"
