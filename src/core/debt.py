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
    
    if state.day >= state.next_payment_day:
        _process_payment()

def _process_payment():
    """Try to take the weekly payment from the player."""
    if state.credits >= state.weekly_payment:
        # Player can afford it
        state.credits -= state.weekly_payment
        state.debt = max(0, state.debt - state.weekly_payment)
        state.missed_payments = 0
        state.add_message(f"Loan payment of {state.weekly_payment} credits deducted.")

        if state.debt == 0:
            state.add_message("Your loan is fully paid off. You own your ship!")

    else:
        # Player can't afford it
        state.missed_payments += 1

        # Apply interest 
        interest = int(state.debt * INTREST_RATE)
        state.debt += interest
        state.weekly_payment = int(state.weekly_payment * (1 - INTREST_RATE))

        msg = ESCALATION.get(state.missed_payments, ESCALATION[4])
        state.add_message(msg)
        state.add_message(f"Interest added: {interest} credits. Debt is now {state.debt}.")

    # Schedule next payment
    state.next_payment_day = state.day + 7