# -*- coding:utf-8 -*-
#
# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the GNU Public License 2 or upper.
# Please ask if you wish a more permissive license.

from dataclasses import dataclass
from os import fstat
from pathlib import Path
from tempfile import NamedTemporaryFile
from subprocess import PIPE, STDOUT, CalledProcessError, CompletedProcess, run
from time import monotonic, sleep
from typing import Generator, List, Optional, Union

from screenutils.errors import ScreenNotFoundError


@dataclass(frozen=True)
class ScreenInfo:
    """Parsed information for one GNU screen session."""

    id: str
    name: str
    status: str
    date: Optional[str] = None


def _run_screen(*args: str, check: bool = True) -> CompletedProcess:
    """Run GNU screen with an argument list, never through a shell."""
    return run(
        ["screen"] + list(args),
        stdout=PIPE,
        stderr=STDOUT,
        universal_newlines=True,
        check=check,
    )


def _screen_output(*args: str) -> str:
    """Run GNU screen and return combined stdout/stderr text.

    Some screen commands, notably ``screen -ls`` when no sessions exist, may
    return a non-zero exit code while still producing useful output.
    """
    try:
        return _run_screen(*args).stdout
    except CalledProcessError as exc:
        return exc.output or ""


def parse_screen_ls(output: str) -> List[ScreenInfo]:
    """Parse ``screen -ls`` output into ``ScreenInfo`` entries."""
    screens = []
    for line in output.splitlines():
        if not line.startswith("\t"):
            continue

        fields = [field for field in line.split("\t") if field]
        if len(fields) < 2 or "." not in fields[0]:
            continue

        id_, name = fields[0].split(".", 1)
        if not id_ or not name:
            continue

        if len(fields) >= 3:
            date = fields[1].strip("()")
            status = fields[2].strip("()")
        else:
            date = None
            status = fields[1].strip("()")

        screens.append(ScreenInfo(id=id_, name=name, date=date, status=status))

    return screens


def _get_screen_infos() -> List[ScreenInfo]:
    return parse_screen_ls(_screen_output("-ls"))


def tailf(
    file_: Union[str, Path],
    interval: float = 0.1,
    encoding: str = "utf-8",
    errors: str = "replace",
    missing_ok: bool = False,
) -> Generator[str, None, None]:
    """Yield content appended to a log file, similar to ``tail -f``.

    The generator preserves the historical behavior of yielding an empty
    string when no new content is available, but it now sleeps briefly between
    empty reads to avoid a busy loop in automation code.

    If ``missing_ok`` is true, missing files are treated like idle reads until
    the file appears. Otherwise, a missing initial file raises
    ``FileNotFoundError``.
    """
    path = Path(file_)
    last_position = 0
    last_identity = None
    initialized = False
    while True:
        try:
            stat = path.stat()
        except FileNotFoundError:
            if not missing_ok:
                raise FileNotFoundError(path)
            last_position = 0
            last_identity = None
            initialized = True
            if interval:
                sleep(interval)
            yield ""
            continue

        identity = (stat.st_dev, stat.st_ino)
        if not initialized:
            last_position = stat.st_size
            last_identity = identity
            initialized = True
            if interval:
                sleep(interval)
            yield ""
            continue

        should_read_from_start = (
            identity != last_identity or stat.st_size < last_position
        )
        read_from = 0 if should_read_from_start else last_position

        if stat.st_size != last_position or should_read_from_start:
            try:
                with path.open("r", encoding=encoding, errors=errors) as f:
                    opened_stat = fstat(f.fileno())
                    opened_identity = (opened_stat.st_dev, opened_stat.st_ino)
                    if (
                        opened_identity != last_identity
                        or opened_stat.st_size < last_position
                    ):
                        read_from = 0
                    f.seek(read_from)
                    text = f.read()
                    last_position = f.tell()
            except FileNotFoundError:
                if not missing_ok:
                    raise
                last_position = 0
                last_identity = None
                if interval:
                    sleep(interval)
                yield ""
                continue

            last_identity = opened_identity
            yield text
        else:
            if interval:
                sleep(interval)
            yield ""


def list_screens() -> List["Screen"]:
    """List all the existing screens and build a Screen instance for each
    """
    return [Screen(info.name) for info in _get_screen_infos()]


class Screen(object):
    """Represents a gnu-screen object::

        >>> s=Screen("screenName", initialize=True)
        >>> s.name
        'screenName'
        >>> s.exists
        True
        >>> s.state
        >>> s.send_commands("man -k keyboard")
        >>> s.kill()
        >>> s.exists
        False
    """

    def __init__(self, name: str, initialize: bool = False) -> None:
        self.name = name
        self._id = None
        self._status = None
        self.logs = None
        self._logfilename = None
        if initialize:
            self.initialize()

    @classmethod
    def create(cls, name: str) -> "Screen":
        """Create a detached screen session and return its ``Screen`` wrapper."""
        screen = cls(name)
        screen.initialize()
        return screen

    @classmethod
    def ensure(cls, name: str) -> "Screen":
        """Return a ``Screen`` wrapper, creating the session if necessary."""
        return cls.create(name)

    @classmethod
    def get(cls, name: str) -> "Screen":
        """Return an existing screen session or raise ``ScreenNotFoundError``."""
        screen = cls(name)
        screen._check_exists()
        return screen

    @property
    def id(self) -> str:
        """return the identifier of the screen as string"""
        if not self._id:
            self._set_screen_infos()
        return self._id

    @property
    def status(self) -> str:
        """return the status of the screen as string"""
        self._set_screen_infos()
        return self._status

    @property
    def exists(self) -> bool:
        """Tell if the screen session exists or not."""
        return any(info.name == self.name for info in _get_screen_infos())

    def enable_logs(
        self,
        filename: Optional[Union[str, Path]] = None,
        interval: float = 0.1,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> None:
        if filename is None:
            filename = self.name
        filename = str(filename)
        self._screen_commands("logfile " + filename, "log on")
        self._logfilename = filename
        Path(filename).touch()
        self.logs = self.tail_logs(interval=interval, encoding=encoding, errors=errors)

    def tail_logs(
        self,
        timeout: Optional[float] = None,
        interval: float = 0.1,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> Generator[str, None, None]:
        """Yield log chunks until ``timeout`` seconds elapse, if provided."""
        if self._logfilename is None:
            raise RuntimeError("Logs are not enabled. Call enable_logs() first.")

        deadline = None if timeout is None else monotonic() + timeout
        logs = tailf(
            self._logfilename,
            interval=interval,
            encoding=encoding,
            errors=errors,
            missing_ok=True,
        )
        while True:
            if deadline is not None:
                remaining = deadline - monotonic()
                if remaining <= 0 or (interval and remaining < interval):
                    return
            yield next(logs)

    def disable_logs(self, remove_logfile: bool = False) -> None:
        self._screen_commands("log off")
        if remove_logfile:
            Path(self._logfilename).unlink()
        self.logs = None

    def initialize(self) -> None:
        """initialize a detached screen, if does not exists yet"""
        if not self.exists:
            self._id = None
            # Create a new detached session without requiring a TTY.
            _run_screen("-dmS", self.name)

    def interrupt(self) -> None:
        """Insert CTRL+C in the screen session"""
        self.ctrl_c()

    def ctrl_c(self) -> None:
        """Insert CTRL+C in the screen session."""
        self._screen_commands("eval \"stuff \\003\"")

    def kill(self) -> None:
        """Kill the screen applications then close the screen"""
        self.quit()

    def quit(self) -> None:
        """Quit the screen session."""
        self._screen_commands('quit')

    def detach(self) -> None:
        """detach the screen"""
        self._check_exists()
        _run_screen("-d", self.id)

    def send_text(self, text: str) -> None:
        """Send raw text to the active GNU screen session."""
        self._check_exists()
        _run_screen("-S", self.id, "-X", "stuff", text)
        sleep(0.02)

    def send_line(self, command: str) -> None:
        """Send one command line to the active GNU screen session."""
        self.send_text(command + "\n")

    def hardcopy(self) -> str:
        """Return the current visible contents of the screen session."""
        self._check_exists()
        with NamedTemporaryFile() as hardcopy_file:
            _run_screen("-S", self.id, "-X", "hardcopy", "-h", hardcopy_file.name)
            return Path(hardcopy_file.name).read_text(errors="replace")

    def send_commands(self, *commands: str) -> None:
        """send commands to the active gnu-screen"""
        for command in commands:
            self.send_line(command)

    def add_user_access(self, unix_user_name: str) -> None:
        """allow to share your session with an other unix user"""
        self._screen_commands('multiuser on', 'acladd ' + unix_user_name)

    def _screen_commands(self, *commands: str) -> None:
        """allow to insert generic screen specific commands
        a glossary of the existing screen command in `man screen`"""
        self._check_exists()
        for command in commands:
            _run_screen("-x", self.id, "-X", command)
            sleep(0.02)

    def _check_exists(self, message: str = "Error code: 404.") -> None:
        """check whereas the screen exist. if not, raise an exception"""
        if not self.exists:
            raise ScreenNotFoundError(message, self.name)

    def _set_screen_infos(self) -> None:
        """set the screen information related parameters"""
        for info in _get_screen_infos():
            if info.name == self.name:
                self._id = info.id
                self._date = info.date
                self._status = info.status
                return
        raise ScreenNotFoundError("While getting info.", self.name)


    def __repr__(self) -> str:
        return "<%s '%s'>" % (self.__class__.__name__, self.name)
