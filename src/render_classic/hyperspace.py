from core import state

def draw(console, width, height):

    if not state.hyperspace_complete:

        title = "Travelling to destination".upper()

        console.print(
            width // 2 - len(title) // 2,
            height // 2 - 3,
            title
        )

        dots = "." * (state.hyperspace_stage + 1)

        console.print(
            width // 2 - len(dots) // 2,
            height // 2,
            dots
        )

    else:

        console.clear()

        title = "HYPERSPACE JUMP COMPLETE"

        console.print(
            width // 2 - len(title) // 2,
            height // 2,
            title,
            fg=(0, 255, 0)
        )