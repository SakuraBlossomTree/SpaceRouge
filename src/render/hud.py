# render/hud.py

from core import state

def draw(console, width, height):

    if state.game_state in ("GALAXY", "SYSTEM"):
        console.print(
            width - 15,
            height - 1,
            f"Credits: {state.credits}"
        )

        fuel_text = f"Fuel: {state.fuel:.2f}/{state.max_fuel:.2f}"
        day_text = f"Day: {state.day}"
        debt_text = f"Debt: {state.debt}"
        payment_due = f"Payment due: {state.next_payment_day}"
        console.print(width - len(fuel_text) - 3, height - 3, fuel_text)

        console.print(width - len(day_text) - 3, height - 5, day_text)
        console.print(width - len(debt_text) - 3, height - 7, debt_text)
        console.print(width - len(payment_due) - 3, height - 9, payment_due)