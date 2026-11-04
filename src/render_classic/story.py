"""Render the STORY screen (typewriter intro text over rain)."""

import textwrap
import time

from core import state

TEXT_WIDTH = 65
TEXT_X = 6
TEXT_Y = 8
MAX_LINES = 20

TYPE_SPEED = 0.05  # seconds per revealed character


def in_text_zone(x, y):
    """Used as a rain skip-zone so drops don't render under the story text."""
    return TEXT_Y <= y <= TEXT_Y + 20 and TEXT_X <= x <= TEXT_X + TEXT_WIDTH


def update(story_text):
    """Advance the typewriter reveal. Call once per frame."""
    if state.story_char_index < len(story_text):
        if time.time() - state.last_story_time > TYPE_SPEED:
            state.story_char_index += 1
            state.last_story_time = time.time()


def draw(console, height, story_text):

    visible_text = story_text[: state.story_char_index]
    wrapped_lines = []
    for line in visible_text.split("\n"):
        if line == "":
            wrapped_lines.append("")
        else:
            wrapped_lines.extend(textwrap.wrap(line, width=TEXT_WIDTH))

    max_top = max(0, len(wrapped_lines) - MAX_LINES)
    if state.story_follow:
        state.story_scroll = max_top
    state.story_scroll = max(0, min(state.story_scroll, max_top))
    if state.story_scroll >= max_top:
        state.story_follow = True
    top = state.story_scroll
    shown = wrapped_lines[top:top + MAX_LINES]
    for i, line in enumerate(shown):
        console.print(TEXT_X, TEXT_Y + i, line)

    # Scrollbar on the right edge when the text is longer than the screen.
    if len(wrapped_lines) > MAX_LINES:
        bar_x, bar_h = 73, MAX_LINES
        for i in range(bar_h):
            console.print(bar_x, TEXT_Y + i, "│", fg=(60, 60, 70))
        thumb_h = max(1, bar_h * MAX_LINES // len(wrapped_lines))
        thumb_y = TEXT_Y + (bar_h - thumb_h) * top // max(1, len(wrapped_lines) - MAX_LINES)
        for i in range(thumb_h):
            console.print(bar_x, thumb_y + i, "█", fg=(90, 130, 150))

    still_typing = state.story_char_index < len(story_text)
    cursor_blink_on = int(time.time() * 2) % 2

    if still_typing and state.story_follow and cursor_blink_on:
        if shown:
            console.print(
                TEXT_X + len(shown[-1]),
                TEXT_Y + (len(shown) - 1),
                "_",
            )
        else:
            console.print(TEXT_X, TEXT_Y, "_")

    hint = "SPACE - Skip    ENTER - Continue"
    if len(wrapped_lines) > MAX_LINES:
        hint += "    UP/DOWN - Scroll"
    console.print(2, height - 2, hint)