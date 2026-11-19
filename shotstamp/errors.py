"""Errors raised by shotstamp.

Kept in one place so the CLI can tell a usage mistake (bad pattern, missing
folder) apart from a per-file problem (a photo it couldn't read), and print a
plain sentence for each instead of a traceback.
"""


class ShotstampError(Exception):
    """A problem the user can actually do something about."""


class BadPatternError(ShotstampError):
    """The --pattern given on the command line can't be used as a filename."""
