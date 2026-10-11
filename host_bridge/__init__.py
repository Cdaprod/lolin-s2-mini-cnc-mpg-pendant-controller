"""Universal host-side endpoint for the smart CNC pendant."""

from .bridge import HostBridge
from .model import MachineState

__all__ = ("HostBridge", "MachineState")
