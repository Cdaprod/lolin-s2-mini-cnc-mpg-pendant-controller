import storage

# Give the USB host write ownership of CIRCUITPY.
# CircuitPython itself remains read-only during normal execution.
storage.remount("/", readonly=True)
