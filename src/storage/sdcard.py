"""Filesystem-backed job discovery and incremental reading."""

import os

JOB_EXTENSIONS = (".nc", ".gcode", ".tap")


class JobFile:
    def __init__(self, path):
        self.path = path
        self.size = os.stat(path)[6]
        self.bytes_read = 0
        self.line_number = 0
        self._file = None

    def open(self):
        self.close()
        self._file = open(self.path, "r")
        self.bytes_read = 0
        self.line_number = 0
        return self

    def next_command(self):
        if self._file is None:
            raise RuntimeError("job is not open")
        while True:
            line = self._file.readline()
            if not line:
                return None
            self.bytes_read += len(line.encode("utf-8"))
            self.line_number += 1
            command = line.split(";", 1)[0].strip()
            if "(" in command:
                command = command.split("(", 1)[0].strip()
            if command:
                return command

    @property
    def progress(self):
        if not self.size:
            return 1.0
        return min(1.0, float(self.bytes_read) / self.size)

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None


class SDStorage:
    def __init__(self, jobs_path="/jobs", macros_path="/macros",
                 config_path="/config"):
        self.jobs_path = jobs_path
        self.macros_path = macros_path
        self.config_path = config_path

    def list_jobs(self):
        try:
            names = os.listdir(self.jobs_path)
        except OSError:
            return []
        return sorted(name for name in names if
                      name.lower().endswith(JOB_EXTENSIONS) and
                      not name.startswith("."))

    def select_job(self, name):
        if name not in self.list_jobs():
            raise ValueError("unknown or unsupported job: " + name)
        return JobFile(self.jobs_path.rstrip("/") + "/" + name)
