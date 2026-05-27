# screenctl

`screenctl` is a small Python library for controlling GNU screen sessions from automation code. It can create and discover sessions, send text or command lines, capture visible output, and manage screen log streams without shelling through user-controlled command strings.

This repository is maintained as the active `screenctl` project. It was renamed from `screenutils` after a modernization pass and is intended to move forward independently.

## Requirements

- Python 3.8 or newer
- GNU screen available as `screen` on `PATH`

## Installation

Install the current development version directly from GitHub:

```bash
python -m pip install git+https://github.com/TutuchanXD/screenctl.git
```

For local development:

```bash
git clone git@github.com:TutuchanXD/screenctl.git
cd screenctl
python -m pip install -e . pytest
pytest
```

## Quick Start

```python
from screenctl import Screen, list_screens

print(list_screens())

session = Screen.create("job")
session.send_line("printf 'hello from screenctl\n'")
print(session.hardcopy())
session.quit()
```

## Public API

### `Screen`

- `Screen(name, initialize=False)`: create a wrapper for a named GNU screen session.
- `Screen.create(name)`: create a detached session and return its wrapper.
- `Screen.ensure(name)`: currently an alias for `create()`.
- `Screen.get(name)`: return an existing session or raise `ScreenNotFoundError`.
- `screen.exists`: return whether the session currently exists.
- `screen.id`: return the GNU screen session id.
- `screen.status`: return the parsed session status.
- `screen.initialize()`: create the session when it does not exist.
- `screen.send_text(text)`: send raw text without adding Enter.
- `screen.send_line(command)`: send text followed by a newline.
- `screen.send_commands(*commands)`: legacy alias that sends each command line.
- `screen.hardcopy()`: return the current visible session contents.
- `screen.enable_logs(filename=None, ...)`: enable GNU screen logging and prepare `screen.logs`.
- `screen.tail_logs(timeout=None, ...)`: stream appended log chunks.
- `screen.disable_logs(remove_logfile=False)`: disable logging and optionally remove the log file.
- `screen.detach()`: detach the session.
- `screen.quit()` / `screen.kill()`: close the session.
- `screen.ctrl_c()` / `screen.interrupt()`: send Ctrl-C to the session.
- `screen.add_user_access(unix_user_name)`: enable GNU screen multi-user access for another Unix user. This may require system-level screen permissions.

### Functions

- `list_screens()`: return all discovered sessions as `Screen` instances.

### Exceptions

- `ScreenNotFoundError`: raised when an operation requires a session that does not exist.

## Testing

Run the normal unit test suite with:

```bash
pytest
```

Integration tests require a real GNU screen binary and are marked with `integration`:

```bash
pytest -m integration
```

## Maintenance Roadmap

The active roadmap is tracked in GitHub issues so status, labels, and discussion stay in one place. Current follow-up work includes:

- [#18: make `Screen.initialize` concurrency-safe](https://github.com/TutuchanXD/screenctl/issues/18)
- [#19: harden log enable and disable lifecycle](https://github.com/TutuchanXD/screenctl/issues/19)
- [#20: make `tailf` robust to log rotation and timeout edge cases](https://github.com/TutuchanXD/screenctl/issues/20)
- [#14: refresh documentation, license, and release workflow](https://github.com/TutuchanXD/screenctl/issues/14)

Completed modernization items are also kept in the issue tracker with the `done` label, including packaging, parser tests, safe subprocess execution, and detached session creation.

## Acknowledgements

`screenctl` originated as a fork of Christophe Narbonne's `screenutils` project: https://github.com/Christophe31/screenutils

The original project is archived and no longer maintained. This repository continues development independently under the `screenctl` name while preserving the project history and prior contributors.

Thanks to the original contributors listed in `CONTRIBUTORS`.

## License

This project is distributed under GPL-3.0-or-later. See [LICENSE](LICENSE).
