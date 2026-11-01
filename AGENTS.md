# FreeCAD process and document handling

- Use the configured `freecad` MCP `execute_code_headless` tool for geometric experiments and validation. Give each call an explicit timeout of at most 180 seconds; use disposable document copies and never let a headless worker and GUI save the same file concurrently.
- Use `freecadcmd` for bounded one-shot jobs. Do not launch the FreeCAD GUI executable for scripts, diagnostics, or rendering. Reuse the existing GUI session for viewport inspection. If a separate GUI is unavoidable, record its PID and document path, save any needed state, then close that exact window before continuing.
- Do not dismiss FreeCAD Recovery or discard a document with unsaved changes. Save recovered documents to distinct recovery filenames before closing or promoting any file.
- After each headless call, confirm the worker exited. On timeout, let the MCP worker cleanup complete before retrying from a fresh copy. Do not launch a second job against the same document while a prior job may still be running.
- Keep searches scoped to the repository or known FreeCAD recovery directories; avoid recursive scans of the entire home Library or temporary filesystem.
