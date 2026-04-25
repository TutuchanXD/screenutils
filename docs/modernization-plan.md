# screenutils Modernization Plan

This document describes a staged modernization plan for `screenutils`, a small Python wrapper around GNU screen. The goal is to make the project safe, testable, Python 3 native, and suitable for automation use cases while preserving the spirit of the original API where practical.

## 1. Project Assessment

`screenutils` currently provides a thin Python interface for:

- Listing GNU screen sessions.
- Creating named screen sessions.
- Sending commands or control sequences into a session.
- Enabling and reading screen logs.
- Detaching or quitting sessions.
- Granting multi-user screen access.

The codebase is intentionally small, but it reflects older Python and shell scripting practices. The most important current limitations are:

- Python 2 compatibility code is still present.
- Packaging uses `distutils` through `setup.py`.
- There is no automated test suite.
- Shell commands are built through string concatenation and executed through `os.system`.
- `screen -ls` output parsing is fragile.
- Session creation uses interactive `screen -UR` plus a delayed detach thread.
- Logging is implemented with a polling generator that can spin too aggressively.
- The public API lacks type hints and modern convenience methods.
- Documentation still contains Python 2 style examples.
- The `LICENCE` file is empty even though the package metadata and source headers refer to GPLv2+.

## 2. Modernization Goals

The modernization should pursue the following goals:

1. Make the project Python 3 native.
2. Replace unsafe shell command construction with safe subprocess calls.
3. Make GNU screen session parsing robust and testable.
4. Make session creation deterministic and non-interactive.
5. Improve log handling for automation workloads.
6. Preserve backward-compatible API entry points where reasonable.
7. Add tests, CI, and clear release metadata.
8. Clarify project maintenance status, licensing, and supported platforms.

Non-goals for the initial modernization:

- Replacing GNU screen with tmux.
- Implementing a full terminal emulator.
- Supporting every advanced GNU screen feature.
- Maintaining Python 2 compatibility.

## 3. Proposed Pull Request Plan

The work should be split into small, reviewable pull requests. Each PR should have a clear scope and should leave the project in a working state.

### PR 1: chore: Modernize Packaging and Drop Python 2 Compatibility

Suggested title:

```text
chore: modernize packaging and drop Python 2 compatibility
```

Purpose:

Establish a modern Python 3 project baseline before deeper refactoring begins.

Scope:

- Add `pyproject.toml` with modern project metadata.
- Declare the supported Python version range, for example `>=3.8` or `>=3.9`.
- Remove Python 2 compatibility imports such as `commands.getoutput`.
- Replace old Python 2 examples in the README.
- Keep `setup.py` only if needed as a compatibility shim, or remove it if the packaging backend supports the desired workflow.
- Add a minimal GitHub Actions CI workflow for install and test commands.
- Add basic development dependencies, such as `pytest` and optionally a linter.

Suggested implementation details:

- Use `setuptools` as the initial backend to minimize migration risk.
- Keep package name and import paths unchanged.
- Do not refactor runtime behavior in this PR except what is required for Python 3 only cleanup.

Acceptance criteria:

- The package can be installed locally with `pip install -e .`.
- `python -m build` works if a build backend is configured.
- The existing public imports still work:

  ```python
  from screenutils import Screen, list_screens, ScreenNotFoundError
  ```

- CI runs successfully.
- README examples use Python 3 syntax.

Risk level: low.

Priority: highest. This PR creates the foundation for all later work.

### PR 2: test: Add Tests and Robust `screen -ls` Parsing

Suggested title:

```text
test: add pytest suite and robust screen -ls parsing
```

Purpose:

Make the most fragile part of the project testable before replacing command execution internals.

Scope:

- Add a pytest test suite.
- Extract `screen -ls` parsing into a pure function.
- Introduce an internal representation for parsed sessions, for example:

  ```python
  @dataclass(frozen=True)
  class ScreenInfo:
      pid: str
      name: str
      status: str | None = None
      date: str | None = None
  ```

- Add tests for typical and edge-case `screen -ls` outputs.
- Update `list_screens()`, `Screen.exists`, `Screen.id`, and `Screen.status` to use the parser.

Test cases should cover:

- No active screen sessions.
- One detached session.
- One attached session.
- Multiple sessions.
- Session names containing dots.
- Session names that are substrings of other names, such as `foo` and `foobar`.
- Unexpected or irrelevant lines in `screen -ls` output.

Acceptance criteria:

- Parser behavior is covered by unit tests.
- `list_screens()` returns the same high-level type as before: a list of `Screen` objects.
- Existing public properties continue to work.
- Session name matching is exact, not substring-based.

Risk level: low to medium.

Priority: high.

### PR 3: fix: Replace Shell Command Construction with Safe Subprocess Calls

Suggested title:

```text
fix: replace shell command construction with safe subprocess calls
```

Purpose:

Remove shell injection risks and make command execution behavior easier to test.

Current risky patterns include:

```python
system('screen -UR ' + self.name)
system('screen -x ' + self.id + ' -X ' + command)
system('rm ' + self._logfilename)
getoutput('screen -ls')
```

Scope:

- Replace `os.system` with `subprocess.run([...], check=True)`.
- Replace `subprocess.getoutput("screen -ls")` with explicit subprocess calls using argument lists.
- Use `pathlib.Path` for log file deletion instead of shelling out to `rm`.
- Add an internal command runner abstraction if helpful for testing.
- Validate screen session names and reject unsafe or empty names.
- Review quoting and escaping around GNU screen `stuff` commands.

Potential internal helper:

```python
def run_screen_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["screen", *args],
        check=True,
        text=True,
        capture_output=True,
    )
```

Acceptance criteria:

- No runtime path uses `os.system`.
- No runtime path uses shell command strings for subprocess execution.
- Log file removal does not call `rm`.
- Unit tests cover command construction through mocks.
- Existing public methods still exist.

Risk level: medium.

Priority: very high. This is the most important security-oriented change.

### PR 4: fix: Create Sessions in Detached Mode Without Attach/Detach Race

Suggested title:

```text
fix: create sessions in detached mode without attach/detach race
```

Purpose:

Make session initialization deterministic and suitable for non-interactive automation environments.

Current behavior:

```python
Thread(target=self._delayed_detach).start()
system('screen -UR ' + self.name)
```

This approach relies on an interactive attach, a background thread, and a fixed sleep interval.

Scope:

- Replace interactive initialization with detached session creation:

  ```bash
  screen -dmS <name>
  ```

- Remove `_delayed_detach()` and the thread-based detach mechanism.
- Keep `Screen(name, initialize=True)` as a compatibility entry point.
- Make initialization a no-op when the session already exists.
- Document behavior clearly.

Acceptance criteria:

- `Screen("name", initialize=True)` creates a detached screen session.
- Initialization does not require a TTY.
- No thread is created for detach behavior.
- Existing `detach()` remains available for manually detaching attached sessions.

Risk level: medium.

Priority: high.

### PR 5: fix: Improve Logging and Tail Support

Suggested title:

```text
fix: improve logging and tail support
```

Purpose:

Make log handling reliable enough for automation workflows.

Scope:

- Improve `tailf()` to avoid busy-spinning.
- Add configurable polling interval.
- Handle file truncation and missing files more gracefully.
- Add explicit encoding and error handling.
- Consider adding a higher-level method such as:

  ```python
  def tail_logs(self, timeout: float | None = None, interval: float = 0.1):
      ...
  ```

- Keep `screen.logs` compatibility if possible.
- Ensure `disable_logs(remove_logfile=True)` uses `Path.unlink()`.

Acceptance criteria:

- Tail logic does not spin in a tight loop.
- Log reading supports Python 3 text handling.
- Log cleanup is safe.
- Unit tests cover truncation and incremental reading.

Risk level: low to medium.

Priority: medium-high.

### PR 6: feat: Add a Modern High-Level API with Type Hints

Suggested title:

```text
feat: add high-level Python 3 API with type hints
```

Purpose:

Improve developer ergonomics while preserving the original API where possible.

Possible new API surface:

```python
from screenutils import Screen

s = Screen.ensure("job")
s.send_line("python train.py")
s.ctrl_c()
s.quit()
```

Potential additions:

- `Screen.create(name)`
- `Screen.ensure(name)`
- `Screen.get(name)`
- `send_text(text)`
- `send_line(command)`
- `ctrl_c()` as a clearer alias for `interrupt()`
- `quit()` as a clearer alias for `kill()`
- Context manager support if semantics are clear.
- Type hints across the public API.

Compatibility guidance:

- Keep `send_commands(*commands)` as an alias or wrapper.
- Keep `interrupt()` and `kill()` unless there is a major-version release.
- Avoid surprising automatic cleanup in `__exit__` unless explicitly documented.

Acceptance criteria:

- New API is documented and tested.
- Existing API continues to work.
- Type hints are present for public methods.

Risk level: low to medium.

Priority: medium.

### PR 7: test: Add Optional GNU screen Integration Tests

Suggested title:

```text
test: add optional GNU screen integration tests
```

Purpose:

Verify that the wrapper actually works against a real GNU screen binary.

Scope:

- Add pytest markers for integration tests.
- Skip integration tests automatically when `screen` is unavailable.
- Test the lifecycle:
  - create session
  - list session
  - send command
  - enable logs
  - read expected output
  - interrupt if needed
  - quit session
- Ensure cleanup runs even on failure.

Acceptance criteria:

- Integration tests can be run locally with a documented command.
- Tests are skipped cleanly when GNU screen is not installed.
- CI either runs them in an environment with screen installed or keeps them optional.

Risk level: medium due to environment variability.

Priority: medium.

### PR 8: docs: Refresh Documentation, License, and Release Workflow

Suggested title:

```text
docs: refresh documentation, license, and release workflow
```

Purpose:

Make the project understandable and releasable after modernization.

Scope:

- Rewrite README for Python 3 users.
- Add examples for common automation workflows.
- Document GNU screen as a system dependency.
- Document security constraints and session name validation.
- Add or fix license text.
- Add `CHANGELOG.md`.
- Add `CONTRIBUTING.md` if future external contributions are expected.
- Add build and release workflow if publishing is planned.

License note:

The source headers and setup metadata refer to GPLv2 or later, but the current `LICENCE` file is empty. This should be corrected before publishing new releases.

Acceptance criteria:

- README accurately reflects the modern API.
- License file is no longer empty.
- Release steps are documented.

Risk level: low.

Priority: medium-low, but important before public release.

## 4. Recommended Execution Strategy

### Minimal Maintainable Version

Implement PRs 1 through 4:

1. Modern packaging and Python 3 baseline.
2. Tests and parser extraction.
3. Safe subprocess command execution.
4. Non-interactive detached session creation.

This makes the project maintainable and much safer without expanding scope too far.

### Practical Automation Version

Implement PRs 1 through 6:

1. Modern packaging.
2. Parser tests.
3. Safe subprocess execution.
4. Detached initialization.
5. Better logging.
6. Modern high-level API.

This makes the library practical for automation tools, background jobs, and agent workflows.

### Full Revival Version

Implement all 8 PRs:

1. Modern packaging.
2. Parser tests.
3. Safe subprocess execution.
4. Detached initialization.
5. Better logging.
6. Modern high-level API.
7. Integration tests.
8. Documentation, license, and release workflow.

This is the right path if the project will be republished or maintained as an active fork.

## 5. Backward Compatibility Policy

Recommended policy:

- Keep existing import paths stable.
- Keep existing method names for at least one modernization release.
- Add clearer aliases instead of immediately removing old names.
- Document changed behavior around initialization, especially replacing interactive `screen -UR` with detached creation.
- If behavior changes are substantial, release as a new minor or major version depending on project versioning policy.

Potential compatibility aliases:

- `send_commands()` remains available and delegates to `send_line()`.
- `interrupt()` remains available and delegates to `ctrl_c()`.
- `kill()` remains available and delegates to `quit()`.

## 6. Security Considerations

The most important security requirement is to avoid shell execution with user-controlled strings.

The following values should be treated as untrusted input:

- Screen session names.
- Commands sent to a session.
- Log file paths.
- Unix user names passed to ACL-related methods.

Recommended safeguards:

- Use `subprocess.run()` with argument lists and `shell=False`.
- Validate session names.
- Use `pathlib.Path` for filesystem operations.
- Avoid implementing shell escaping manually unless GNU screen itself requires a specific syntax.
- Add tests for names and commands containing spaces or special characters.

## 7. Open Questions

Before starting implementation, decide:

1. What minimum Python version should be supported?
2. Should this fork keep the package name `screenutils`, or use a new name if republished?
3. Should `Screen.kill()` remain the preferred method, or should `quit()` become primary?
4. Should multi-user ACL support remain, given the system-level permission implications?
5. Should the project maintain GPLv2+ licensing, or only clarify the existing license file?
6. Should integration tests run in CI by default, or only locally/on demand?

## 8. Suggested PR 1 Checklist

For the immediate next step, PR 1 should include:

- [ ] Add `pyproject.toml`.
- [ ] Declare Python 3 support only.
- [ ] Remove Python 2-only import fallback.
- [ ] Update README examples to Python 3 syntax.
- [ ] Add a minimal pytest setup.
- [ ] Add GitHub Actions CI.
- [ ] Confirm `pip install -e .` works.
- [ ] Confirm public imports still work.

