"""ARCHIVED: the weekly-instalment loan system (removed from the live game).

Nothing imports this file. It is the old core/debt.py, kept so the instalments
can come back. To restore: use this as core/debt.py, and put back
  * core/state.py:   weekly_payment = 1000, missed_payments = 0,
                     next_payment_day = 14, paid_this_cycle = 0
                     (and starting_debt was 250000)
  * core/events.py:  `state.paid_this_cycle += amount` in _pay_debt()
  * render/hud.py:   the Loan panel rows Instalment / Due / Strikes
  * render/location.py: the "Next installment" / "Paid early" rows in _draw_debt
  * render/help.py + core/tutorial.py: the Instalments / Strikes text
  * render_classic/hud.py: the "Payment due" line
Early payments (Pay Debt) counted toward the next instalment; four missed
payments in a row was game over.
"""

'''Debt and loan repayment system.'''

from core import state

INTREST_RATE = 0.02 # 2% per missed payment

# Escalation messages per missed payment count
ESCALATION = {
    1: "WARNING: You have missed a loan payment. Pay immediately.",
    2: "Your interest rate has increased due to missed payments.",
    3: "Debt collectors have been dispatched to find you.",
    4: "Bounty hunters have been hired to collect your debt.",
}

def advance_day():
    """Called every time a day passes. Checkd if payment is due."""
    state.day += 1

    # the galaxy economy moves on: NPC trades, prices, stocks, news
    from core import economy
    economy.tick()
    
    if state.day >= state.next_payment_day:
        _process_payment()

def _process_payment():
    """Try to take the weekly payment from the player."""
    if state.debt <= 0:
        state.next_payment_day = state.day + 7
        return

    # Early payments made since the last installment count toward this one,
    # and the installment is never more than what is still owed.
    due = min(state.weekly_payment, state.debt)
    owed = max(0, due - state.paid_this_cycle)
    state.paid_this_cycle = 0

    if owed == 0:
        state.missed_payments = 0
        state.add_message("Your early payments covered this week's installment.")

    elif state.credits >= owed:
        # Player can afford it
        state.credits -= owed
        state.debt = max(0, state.debt - owed)
        state.missed_payments = 0
        state.add_message(f"Loan payment of {owed} credits deducted.")

        if state.debt == 0:
            state.add_message("Your loan is fully paid off. You own your ship!")

    else:
        # Player can't afford it
        state.missed_payments += 1

        # Apply interest 
        interest = int(state.debt * INTREST_RATE)
        state.debt += interest
        state.weekly_payment = int(state.weekly_payment * (1 + INTREST_RATE))

        msg = ESCALATION.get(state.missed_payments, ESCALATION[4])
        state.add_message(msg)
        state.add_message(f"Interest added: {interest} credits. Debt is now {state.debt}.")

        if state.missed_payments >= 4:
            state.game_over_reason = "Bounty hunters caught up with you. Your debt went unpaid."
            state.game_state = "GAME_OVER"

    # Schedule next payment
    state.next_payment_day = state.day + 7