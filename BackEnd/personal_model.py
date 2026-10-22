# FocusSense - Adaptive Personal Model

personal_data = {
    "sessions": 0,
    "total_productive_time": 0,
    "total_distractive_time": 0,
    "total_distractions": 0,
    "total_recovery_time": 0,
    "recovery_count": 0,
    "total_task_switches": 0,
    "common_distractions": {},
    "productive_exceptions": {}
}


def update_personal_model(
    classification,
    duration,
    recovery_time=None,
    task_switches=0,
    distraction_window=None
):
    """
    Update the student's personal behavior model.
    """

    # -----------------------------------------
    # Productive activity
    # -----------------------------------------

    if classification == "Productive":

        personal_data["total_productive_time"] += duration

    # -----------------------------------------
    # Distractive activity
    # -----------------------------------------

    elif classification == "Distractive":

        personal_data["total_distractive_time"] += duration

        personal_data["total_distractions"] += 1

        if distraction_window:

            window = distraction_window.lower()

            personal_data["common_distractions"][window] = (
                personal_data["common_distractions"].get(window, 0) + 1
            )

    # -----------------------------------------
    # Productive Exception
    # -----------------------------------------

    elif classification == "Productive Exception":

        if distraction_window:

            personal_data["productive_exceptions"][
                distraction_window
            ] = (
                personal_data["productive_exceptions"].get(
                    distraction_window, 0
                ) + 1
            )

        personal_data["total_productive_time"] += duration

    # -----------------------------------------
    # Recovery Time
    # -----------------------------------------

    if recovery_time is not None:

        personal_data["total_recovery_time"] += recovery_time

        personal_data["recovery_count"] += 1

    # -----------------------------------------
    # Task Switching
    # -----------------------------------------

    # IMPORTANT:
    # Add only the NEW task switches received
    # instead of repeatedly adding the cumulative count.

    if task_switches > 0:

        personal_data["total_task_switches"] += task_switches

    # -----------------------------------------
    # Return updated profile
    # -----------------------------------------

    return get_personal_profile()


def get_personal_profile():

    # -----------------------------------------
    # Average recovery time
    # -----------------------------------------

    if personal_data["recovery_count"] > 0:

        average_recovery = (
            personal_data["total_recovery_time"]
            / personal_data["recovery_count"]
        )

    else:

        average_recovery = 0

    # -----------------------------------------
    # Total activity time
    # -----------------------------------------

    total_time = (
        personal_data["total_productive_time"]
        + personal_data["total_distractive_time"]
    )

    # -----------------------------------------
    # Productive percentage
    # -----------------------------------------

    if total_time > 0:

        productive_percentage = (
            personal_data["total_productive_time"]
            / total_time
        ) * 100

    else:

        productive_percentage = 0

    # -----------------------------------------
    # Most common distraction
    # -----------------------------------------

    if personal_data["common_distractions"]:

        common_distraction = max(
            personal_data["common_distractions"],
            key=personal_data["common_distractions"].get
        )

    else:

        common_distraction = "None"

    # -----------------------------------------
    # Most common productive exception
    # -----------------------------------------

    if personal_data["productive_exceptions"]:

        productive_exception = max(
            personal_data["productive_exceptions"],
            key=personal_data["productive_exceptions"].get
        )

    else:

        productive_exception = "None"

    # -----------------------------------------
    # PROFILE
    # -----------------------------------------

    return {
        "sessions": personal_data["sessions"],

        "productive_time": round(
            personal_data["total_productive_time"],
            2
        ),

        "distractive_time": round(
            personal_data["total_distractive_time"],
            2
        ),

        "productive_percentage": round(
            productive_percentage,
            2
        ),

        "total_distractions":
            personal_data["total_distractions"],

        "average_recovery_time": round(
            average_recovery,
            2
        ),

        "task_switches":
            personal_data["total_task_switches"],

        "common_distraction":
            common_distraction,

        "productive_exception":
            productive_exception
    }


def start_session():

    personal_data["sessions"] += 1

    return personal_data["sessions"]
