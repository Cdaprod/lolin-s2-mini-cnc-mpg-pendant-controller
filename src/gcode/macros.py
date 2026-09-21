"""Named, file-backed macros executed through the checked GRBL queue."""

import os


class MacroLibrary:
    def __init__(self, path="/macros"):
        self.path = path

    def list(self):
        try:
            names = os.listdir(self.path)
        except OSError:
            return []
        return sorted(name[:-6] for name in names
                      if name.lower().endswith(".gcode"))

    def load(self, name):
        if not name or "/" in name or "\\" in name:
            raise ValueError("invalid macro name")
        path = self.path.rstrip("/") + "/" + name + ".gcode"
        commands = []
        with open(path, "r") as source:
            for raw in source:
                command = raw.split(";", 1)[0].strip()
                if command:
                    commands.append(command)
                if len(commands) > 32:
                    raise ValueError("macro exceeds 32-command limit")
        if not commands:
            raise ValueError("macro is empty")
        return commands

    def queue(self, name, controller, safety):
        safety.require_command(motion=True)
        commands = self.load(name)
        if len(commands) + len(controller.queue) > controller.queue_limit:
            raise RuntimeError("macro exceeds available command queue")
        for command in commands:
            controller.queue_command(command, "macro")
        return len(commands)
