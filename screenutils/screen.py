# -*- coding:utf-8 -*-
#
# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the GNU Public License 2 or upper.
# Please ask if you wish a more permissive license.

from dataclasses import dataclass
from pathlib import Path
from subprocess import PIPE, STDOUT, CalledProcessError, run
from os.path import getsize
from time import sleep

from screenutils.errors import ScreenNotFoundError


@dataclass(frozen=True)
class ScreenInfo:
    """Parsed information for one GNU screen session."""

    id: str
    name: str
    status: str
    date: str = None


def _run_screen(*args, check=True):
    """Run GNU screen with an argument list, never through a shell."""
    return run(
        ["screen"] + list(args),
        stdout=PIPE,
        stderr=STDOUT,
        universal_newlines=True,
        check=check,
    )


def _screen_output(*args):
    """Run GNU screen and return combined stdout/stderr text.

    Some screen commands, notably ``screen -ls`` when no sessions exist, may
    return a non-zero exit code while still producing useful output.
    """
    try:
        return _run_screen(*args).stdout
    except CalledProcessError as exc:
        return exc.output or ""


def parse_screen_ls(output):
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


def _get_screen_infos():
    return parse_screen_ls(_screen_output("-ls"))


def tailf(file_):
    """Each value is content added to the log file since last value return"""
    last_size = getsize(file_)
    while True:
        cur_size = getsize(file_)
        if (cur_size != last_size):
            f = open(file_, 'r')
            f.seek(last_size if cur_size > last_size else 0)
            text = f.read()
            f.close()
            last_size = cur_size
            yield text
        else:
            yield ""


def list_screens():
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

    def __init__(self, name, initialize=False):
        self.name = name
        self._id = None
        self._status = None
        self.logs = None
        self._logfilename = None
        if initialize:
            self.initialize()

    @property
    def id(self):
        """return the identifier of the screen as string"""
        if not self._id:
            self._set_screen_infos()
        return self._id

    @property
    def status(self):
        """return the status of the screen as string"""
        self._set_screen_infos()
        return self._status

    @property
    def exists(self):
        """Tell if the screen session exists or not."""
        return any(info.name == self.name for info in _get_screen_infos())

    def enable_logs(self, filename=None):
        if filename is None:
            filename = self.name
        self._screen_commands("logfile " + filename, "log on")
        self._logfilename = filename
        open(filename, 'w+')
        self.logs = tailf(filename)

    def disable_logs(self, remove_logfile=False):
        self._screen_commands("log off")
        if remove_logfile:
            Path(self._logfilename).unlink()
        self.logs = None

    def initialize(self):
        """initialize a detached screen, if does not exists yet"""
        if not self.exists:
            self._id = None
            # Create a new detached session without requiring a TTY.
            _run_screen("-dmS", self.name)

    def interrupt(self):
        """Insert CTRL+C in the screen session"""
        self._screen_commands("eval \"stuff \\003\"")

    def kill(self):
        """Kill the screen applications then close the screen"""
        self._screen_commands('quit')

    def detach(self):
        """detach the screen"""
        self._check_exists()
        _run_screen("-d", self.id)

    def send_commands(self, *commands):
        """send commands to the active gnu-screen"""
        self._check_exists()
        for command in commands:
            self._screen_commands('stuff "' + command + '" ',
                                  'eval "stuff \\015"')

    def add_user_access(self, unix_user_name):
        """allow to share your session with an other unix user"""
        self._screen_commands('multiuser on', 'acladd ' + unix_user_name)

    def _screen_commands(self, *commands):
        """allow to insert generic screen specific commands
        a glossary of the existing screen command in `man screen`"""
        self._check_exists()
        for command in commands:
            _run_screen("-x", self.id, "-X", command)
            sleep(0.02)

    def _check_exists(self, message="Error code: 404."):
        """check whereas the screen exist. if not, raise an exception"""
        if not self.exists:
            raise ScreenNotFoundError(message, self.name)

    def _set_screen_infos(self):
        """set the screen information related parameters"""
        for info in _get_screen_infos():
            if info.name == self.name:
                self._id = info.id
                self._date = info.date
                self._status = info.status
                return
        raise ScreenNotFoundError("While getting info.", self.name)


    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.name)
