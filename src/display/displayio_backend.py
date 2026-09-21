"""Retained-object CircuitPython DisplayIO renderer for UI view models."""


class _DisplayIOTextLine:
    """Fixed bitmap text line using built-in terminalio glyphs only."""

    def __init__(self, width, height, font, displayio, color=0xFFFFFF):
        self.width = width
        self.height = height
        self.font = font
        self.bitmap = displayio.Bitmap(width, height, 2)
        palette = displayio.Palette(2)
        palette[0] = 0x000000
        palette[1] = color
        palette.make_transparent(0)
        self.node = displayio.TileGrid(self.bitmap, pixel_shader=palette)
        self.text = None

    def set_text(self, text):
        text = str(text)
        if text == self.text:
            return False
        self.text = text
        self.bitmap.fill(0)
        cursor = 0
        for character in text:
            glyph = self.font.get_glyph(ord(character))
            if glyph is None:
                continue
            if cursor + glyph.width > self.width:
                break
            source = glyph.bitmap
            columns = max(1, source.width // glyph.width)
            source_x = (glyph.tile_index % columns) * glyph.width
            source_y = (glyph.tile_index // columns) * glyph.height
            for y in range(min(glyph.height, self.height)):
                for x in range(glyph.width):
                    if source[source_x + x, source_y + y]:
                        target_x = cursor + x
                        if target_x < self.width:
                            self.bitmap[target_x, y] = 1
            cursor += max(1, glyph.shift_x)
        return True


class _FakeFriendlyLine:
    """Protocol documentation for injected host-test retained lines."""

    node = None

    def set_text(self, text):
        raise NotImplementedError


class DisplayIOBackend:
    """Render HMI models with bounded retained header/body/footer/overlay rows."""

    def __init__(self, display, width=None, height=None, line_height=14,
                 line_factory=None, group_factory=None):
        self.display = display
        self.width = int(width or display.width)
        self.height = int(height or display.height)
        self.line_height = int(line_height)
        self.ui = None
        self.last_signature = None
        self.render_count = 0
        self.skipped_count = 0
        if line_factory is None or group_factory is None:
            import displayio
            import terminalio
            group_factory = displayio.Group

            def line_factory(line_width, line_height):
                return _DisplayIOTextLine(
                    line_width, line_height, terminalio.FONT, displayio
                )
        self.root = group_factory()
        self.header_group = group_factory()
        self.body_group = group_factory()
        self.footer_group = group_factory()
        self.overlay_group = group_factory()
        for group in (self.header_group, self.body_group, self.footer_group,
                      self.overlay_group):
            self.root.append(group)
        available_rows = max(4, self.height // self.line_height)
        body_count = min(8, max(1, available_rows - 3))
        self.header = line_factory(self.width, self.line_height)
        self.body = [line_factory(self.width, self.line_height)
                     for _ in range(body_count)]
        self.footer = line_factory(self.width, self.line_height)
        self.overlay = line_factory(self.width, self.line_height * 2)
        self.header_group.append(self.header.node)
        for index, line in enumerate(self.body):
            line.node.y = (index + 1) * self.line_height
            self.body_group.append(line.node)
        self.footer.node.y = (body_count + 1) * self.line_height
        self.footer_group.append(self.footer.node)
        self.overlay.node.y = max(0, (available_rows // 2) * self.line_height)
        self.overlay_group.append(self.overlay.node)
        self.display.root_group = self.root

    def bind_ui(self, ui):
        self.ui = ui

    def _home_lines(self, state):
        coordinates = state.displayed_position()
        lines = []
        for axis in ("X", "Y", "Z", "A", "B", "C"):
            value = coordinates.get(axis)
            marker = ">" if axis == state.selected_axis else " "
            shown = "---" if value is None else "{:+.3f}".format(value)
            lines.append("{}{} {}".format(marker, axis, shown))
        return lines

    def _model_lines(self, model, state):
        if model["screen"] == "HOME":
            body = self._home_lines(state)
            footer = "{} {:.3f} {}".format(
                state.selected_multiplier, state.jog_increment,
                state.active_coordinate_system or "---"
            )
        else:
            body = []
            for index, item in enumerate(model.get("items", ())):
                marker = ">" if index == model.get("selected") else " "
                suffix = "" if item[1] else " [X]"
                body.append("{}{}{}".format(marker, item[0], suffix))
            if "filename" in model:
                body.insert(0, "File: {}".format(model["filename"] or "---"))
            if "macro" in model:
                body.insert(0, "Macro: {}".format(model["macro"] or "---"))
            if "text" in model:
                body = [model["text"] + "_",
                        "[{}] {}".format(model["character"], model["group"])]
            for label, value in model.get("details", ()):
                body.append("{}: {}".format(label, value))
            if model["screen"] == "ACTIVE_JOB":
                body.extend(("{:5.1f}% {}".format(
                    model["progress"] * 100, model["stream_state"]),
                    "F{:.0f} S{:.0f}".format(model["feed"], model["spindle"])))
            footer = model["wheel_mode"]
        header = "{} {}".format(model["title"], state.machine_state.upper())
        overlay = model["overlay"][1] if model.get("overlay") else ""
        return header, body, footer, overlay

    def render(self, state):
        if self.ui is None:
            raise RuntimeError("DisplayIOBackend must be bound to UIManager")
        model = self.ui.view_model()
        header, body, footer, overlay = self._model_lines(model, state)
        signature = (header, tuple(body[:len(self.body)]), footer, overlay)
        if signature == self.last_signature:
            self.skipped_count += 1
            return False
        self.last_signature = signature
        self.header.set_text(header)
        for index, line in enumerate(self.body):
            line.set_text(body[index] if index < len(body) else "")
        self.footer.set_text(footer)
        self.overlay.set_text(overlay)
        self.render_count += 1
        try:
            self.display.refresh(minimum_frames_per_second=0)
        except (AttributeError, RuntimeError):
            # Auto-refresh displays need no explicit refresh; a busy display is
            # retried on a later cooperative poll rather than blocking.
            pass
        return True


def from_config(config):
    """Use an existing board.DISPLAY only; no LCD controller or pins assumed."""
    if not config.get("display_enabled"):
        return None
    if not config.get("display_use_board_display"):
        raise ValueError(
            "display enabled but no verified board.DISPLAY integration selected"
        )
    import board
    display = getattr(board, "DISPLAY", None)
    if display is None:
        raise RuntimeError("configured board.DISPLAY is unavailable")
    rotation = config.get("display_rotation", 0)
    if rotation:
        display.rotation = rotation
    return DisplayIOBackend(
        display, config.get("display_width") or None,
        config.get("display_height") or None
    )
