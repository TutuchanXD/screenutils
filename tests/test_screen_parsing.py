import pytest

from screenutils.errors import ScreenNotFoundError
from screenutils.screen import Screen, ScreenInfo, list_screens, parse_screen_ls


NO_SCREENS = """No Sockets found in /run/screen/S-user.
"""

SINGLE_DETACHED = """There is a screen on:
	28062.session1	(Detached)
1 Socket in /run/screen/S-user.
"""

SINGLE_ATTACHED_WITH_DATE = """There is a screen on:
	1234.session2	(04/24/2026 05:30:00 PM)	(Attached)
1 Socket in /run/screen/S-user.
"""

MULTIPLE_SCREENS = """There are screens on:
	111.foo	(Detached)
	222.foo.bar	(Attached)
	333.foobar	(Detached)
3 Sockets in /run/screen/S-user.
"""

IRRELEVANT_LINES = """There are screens on:
not a session line
	missingdot	(Detached)
	444.valid	(Detached)
1 Socket in /run/screen/S-user.
"""


def test_parse_screen_ls_returns_empty_list_when_no_screens_exist():
    assert parse_screen_ls(NO_SCREENS) == []


def test_parse_screen_ls_parses_single_detached_session():
    assert parse_screen_ls(SINGLE_DETACHED) == [
        ScreenInfo(id="28062", name="session1", date=None, status="Detached")
    ]


def test_parse_screen_ls_parses_session_with_date_and_status():
    assert parse_screen_ls(SINGLE_ATTACHED_WITH_DATE) == [
        ScreenInfo(
            id="1234",
            name="session2",
            date="04/24/2026 05:30:00 PM",
            status="Attached",
        )
    ]


def test_parse_screen_ls_preserves_dots_in_session_names():
    assert parse_screen_ls(MULTIPLE_SCREENS)[1] == ScreenInfo(
        id="222", name="foo.bar", date=None, status="Attached"
    )


def test_parse_screen_ls_ignores_irrelevant_lines():
    assert parse_screen_ls(IRRELEVANT_LINES) == [
        ScreenInfo(id="444", name="valid", date=None, status="Detached")
    ]


def test_list_screens_uses_parsed_session_names(monkeypatch):
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: MULTIPLE_SCREENS)

    screens = list_screens()

    assert [screen.name for screen in screens] == ["foo", "foo.bar", "foobar"]
    assert all(isinstance(screen, Screen) for screen in screens)


def test_screen_exists_uses_exact_session_name_matching(monkeypatch):
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: MULTIPLE_SCREENS)

    assert Screen("foo").exists is True
    assert Screen("foo.bar").exists is True
    assert Screen("foobar").exists is True
    assert Screen("fo").exists is False


def test_screen_info_properties_use_exact_session_name_matching(monkeypatch):
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: MULTIPLE_SCREENS)

    screen = Screen("foo.bar")

    assert screen.id == "222"
    assert screen.status == "Attached"


def test_screen_info_properties_raise_for_missing_session(monkeypatch):
    monkeypatch.setattr("screenutils.screen._screen_output", lambda *args: MULTIPLE_SCREENS)

    with pytest.raises(ScreenNotFoundError):
        Screen("missing").id


def test_parse_screen_ls_accepts_statuses_containing_dots():
    output = """There is a screen on:
	555.worker	(Multi, detached)
1 Socket in /run/screen/S-user.
"""

    assert parse_screen_ls(output) == [
        ScreenInfo(id="555", name="worker", date=None, status="Multi, detached")
    ]
