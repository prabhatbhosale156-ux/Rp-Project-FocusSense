# FocusSense - Distraction Recovery Time Engine

recovery_start_time = None
is_recovering = False


def calculate_recovery(
    classification,
    current_time,
    previous_classification
):
    global recovery_start_time
    global is_recovering

    result = {
        "recovery_started": False,
        "recovery_completed": False,
        "recovery_time": None
    }

    # -----------------------------------------
    # 1. Distraction starts
    # -----------------------------------------

    if (
        classification == "Distractive"
        and previous_classification != "Distractive"
        and not is_recovering
    ):

        recovery_start_time = current_time
        is_recovering = True

        result["recovery_started"] = True

        return result

    # -----------------------------------------
    # 2. Student returns to productive activity
    # -----------------------------------------

    if (
        classification == "Productive"
        and is_recovering
        and recovery_start_time is not None
    ):

        recovery_time = round(
            current_time - recovery_start_time,
            2
        )

        result["recovery_completed"] = True
        result["recovery_time"] = recovery_time

        # Reset recovery state
        recovery_start_time = None
        is_recovering = False

        return result

    return result
