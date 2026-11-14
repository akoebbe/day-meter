"""Build a display adapter from secrets config.

secrets["display"] names the adapter; default "bicolor24" (an existing
mysecrets.py without the key keeps working). Adding a new display type =
a new adapter class + one entry here.
"""
from .bicolor24 import Bicolor24Adapter

_DEFAULT = "bicolor24"

_DISPLAYS = {
    "bicolor24": Bicolor24Adapter,
}


def build_display(secrets):
    name = secrets.get("display", _DEFAULT)
    if name not in _DISPLAYS:
        print("Unknown display type: {0!r} (known: {1})".format(
            name, ", ".join(sorted(_DISPLAYS))))
        raise ValueError(name)
    return _DISPLAYS[name]()
