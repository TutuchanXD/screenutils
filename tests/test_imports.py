from screenctl import Screen, ScreenNotFoundError, list_screens


def test_public_imports_are_available():
    assert Screen is not None
    assert ScreenNotFoundError is not None
    assert callable(list_screens)
