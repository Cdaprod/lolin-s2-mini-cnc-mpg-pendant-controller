"""Bounded, one-line-at-a-time GRBL send-response streamer."""


class GCodeStreamer:
    def __init__(self, state, controller, timeout=5.0, clock=None):
        self.state = state
        self.controller = controller
        self.timeout = float(timeout)
        self.clock = clock
        self.job = None
        self.awaiting = False
        self.last_send = None
        self._resume_state = "streaming"
        controller.add_observer(self.on_controller_event)

    def start(self, job, now=None):
        if self.state.estop_observed:
            raise RuntimeError("E-stop observed")
        if self.state.machine_state != "idle":
            raise RuntimeError("controller is not idle")
        self.job = job.open()
        self.state.current_filename = job.path.rsplit("/", 1)[-1]
        self.state.sd_job_state = "streaming"
        self.state.streaming_progress = 0.0
        self.state.streaming_line = 0
        self.state.streaming_bytes = 0
        self.awaiting = False
        self.last_send = now

    def pause(self):
        if self.state.sd_job_state == "streaming":
            self._resume_state = "streaming"
            self.state.sd_job_state = "paused"
            self.controller.realtime("hold")

    def resume(self):
        if self.state.sd_job_state == "paused" and not self.state.estop_observed:
            self.controller.realtime("start")
            self.state.sd_job_state = self._resume_state

    def cancel(self):
        self.controller.realtime("hold")
        self.controller.cancel_jog()
        self.controller.discard_queued("stream")
        self._finish("cancelled")

    def inhibit(self):
        """Stop producing/sending file commands after an observed safety event."""
        self.controller.realtime("hold")
        self.controller.discard_queued("stream")
        self._finish("inhibited")

    def _finish(self, result):
        if self.job:
            self.job.close()
        self.job = None
        self.awaiting = False
        self.state.sd_job_state = result

    def on_controller_event(self, event, value):
        if self.job is None:
            return
        if event == "ok" and value and value[1] == "stream":
            self.awaiting = False
            self.state.streaming_progress = self.job.progress
            self.state.streaming_line = self.job.line_number
            self.state.streaming_bytes = self.job.bytes_read
        elif event == "sent" and value and value[1] == "stream":
            if self.clock:
                self.last_send = self.clock()
        elif event in ("error", "alarm"):
            self.state.error = str(value)
            self._finish(event)

    def poll(self, now=None):
        if self.job is None or self.state.sd_job_state != "streaming":
            return
        if self.state.estop_observed or self.state.estop_latched:
            self._finish("inhibited")
            return
        if self.awaiting:
            if (now is not None and self.last_send is not None and
                    now - self.last_send > self.timeout):
                self.state.error = "stream response timeout"
                self._finish("error")
            return
        try:
            command = self.job.next_command()
        except OSError as exc:
            self.state.error = "job read failed: {}".format(type(exc).__name__)
            self._finish("error")
            return
        if command is None:
            self.state.streaming_progress = 1.0
            self._finish("complete")
            return
        if self.controller.queue_command(command, "stream"):
            self.awaiting = True
            self.last_send = now if now is not None else (
                self.clock() if self.clock else 0.0
            )
