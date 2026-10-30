"""Shared viewport geometry for physical and touch menu selection."""


def menu_window_start(selected, total, visible=6):
    """Keep selected row near center, clamped at both ends."""
    if total <= visible:
        return 0
    return max(0, min(int(selected) - 2, total - visible))
