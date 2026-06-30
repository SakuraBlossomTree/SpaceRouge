"""Render the STORY screen (typewriter intro text over rain)."""

import textwrap
import time

from core import state

TEXT_WIDTH = 65
TEXT_X = 6
TEXT_Y = 8

TYPE_SPEED = 0.03  # seconds per revealed character


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
    wrapped_lines = textwrap.wrap(visible_text, width=TEXT_WIDTH)

    for i, line in enumerate(wrapped_lines):
        console.print(TEXT_X, TEXT_Y + (i * 2), line)

    still_typing = state.story_char_index < len(story_text)
    cursor_blink_on = int(time.time() * 2) % 2

    if still_typing and cursor_blink_on:
        if wrapped_lines:
            console.print(
                TEXT_X + len(wrapped_lines[-1]),
                TEXT_Y + ((len(wrapped_lines) - 1) * 2),
                "_",
            )
        else:
            console.print(TEXT_X, TEXT_Y, "_")

    console.print(2, height - 2, "SPACE - Skip    ENTER - Continue")