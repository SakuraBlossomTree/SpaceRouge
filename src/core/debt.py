"""The loan: one number the player pays down whenever they like, by a deadline.

There are no instalments. Money goes in through the Pay Debt panel at any
station (core/events.py: _pay_debt). If the debt is not cleared by
state.loan_deadline_day the lender repossesses the ship (game over); clearing
it shows the victory screen. The old weekly-instalment system is archived in
core/debt_installments.py.
"""

from core import state

WARN_AT = (90, 30, 14, 7, 3, 1)      # days left at which the lender sends a reminder


def loan_days():
    """How many days a fresh loan lasts (day 1 up to the deadline day)."""
    return state.STARTING_DEADLINE_DAY - 1


def days_left():
    """Days until the lender wants the ship (0 or less = deadline reached)."""
    return state.loan_deadline_day - state.day


def advance_day():
    """Called every time a day passes."""
    state.day += 1

    # the galaxy economy moves on (NPC trades, prices, stocks, news), but in
    # steps of PRICE_UPDATE_DAYS so prices hold still between updates
    from core import economy, market_intel, save
    if state.day % economy.PRICE_UPDATE_DAYS == 0:
        economy.tick(economy.PRICE_UPDATE_DAYS)

    # Scanner records are a separate layer: refresh only what is in range,
    # then persist the player's intelligence alongside the seed.
    market_intel.refresh()
    save.save_progress()

    left = days_left()
    if state.debt > 0 and left in WARN_AT:
        state.add_message(f"WARNING: the lender wants the loan back in {left} day"
                          f"{'s' if left != 1 else ''}.")


def check_deadline():
    """Game over once the deadline passes with debt left. Returns True if it
    ended the run. Called after a jump lands and after the move clock ticks
    (not inside advance_day: the jump animation would overwrite the screen)."""
    if state.debt <= 0 or state.game_state in ("GAME_OVER", "VICTORY"):
        return False
    if days_left() > 0:
        return False
    state.autopilot = None
    state.game_over_reason = ("The lender repossessed the Rogue: the loan "
                              "wasn't repaid in time.")
    state.game_state = "GAME_OVER"
    return True
