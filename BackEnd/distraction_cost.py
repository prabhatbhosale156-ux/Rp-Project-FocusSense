# FocusSense - Distraction Cost Engine

def calculate_distraction_cost(
    duration,
    recovery_time,
    task_switches,
    repeated_distractions
):
    """
    Calculate the overall impact of a distraction.
    """

    score = 0

    # -----------------------------------------
    # 1. Distraction duration
    # -----------------------------------------

    if duration <= 30:
        score += 1
    elif duration <= 120:
        score += 2
    else:
        score += 3

    # -----------------------------------------
    # 2. Recovery time
    # -----------------------------------------

    if recovery_time is not None:

        if recovery_time <= 30:
            score += 1

        elif recovery_time <= 120:
            score += 2

        else:
            score += 3

    # -----------------------------------------
    # 3. Task switching
    # -----------------------------------------

    if task_switches <= 2:
        score += 1

    elif task_switches <= 5:
        score += 2

    else:
        score += 3

    # -----------------------------------------
    # 4. Repeated distractions
    # -----------------------------------------

    if repeated_distractions <= 1:
        score += 1

    elif repeated_distractions <= 3:
        score += 2

    else:
        score += 3

    # -----------------------------------------
    # Final Cost
    # -----------------------------------------

    if score <= 4:
        cost = "Low"

    elif score <= 8:
        cost = "Medium"

    else:
        cost = "High"

    return {
        "score": score,
        "cost": cost
    }
