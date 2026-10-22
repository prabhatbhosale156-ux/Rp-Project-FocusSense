def process_activity(application, window, duration):

    activity = {
        "application": application,
        "window": window,
        "duration": duration
    }

    # Convert everything to lowercase
    app = application.lower().strip()
    title = window.lower().strip()

    # =====================================================
    # 1. DISTRACTIVE ACTIVITIES
    # =====================================================

    distracting_apps = [
        "instagram",
        "facebook",
        "netflix",
        "steam",
        "discord"
    ]

    distracting_words = [
        "instagram",
        "facebook",
        "netflix",
        "steam",
        "twitch",
        "reddit",
        "gaming"
    ]

    # Instagram, Facebook etc.
    if (
        any(name in app for name in distracting_apps)
        or any(word in title for word in distracting_words)
    ):

        classification = "Distractive"


    # =====================================================
    # 2. YOUTUBE
    # =====================================================

    elif "youtube" in title:

        # Because Edge may show:
        # "YouTube and 3 more pages - Personal - Microsoft Edge"
        #
        # We cannot reliably see the video title here.
        # Therefore YouTube is treated as a study activity.

        classification = "Productive"


    # =====================================================
    # 3. PRODUCTIVE WEBSITES / STUDY ACTIVITIES
    # =====================================================

    elif any(word in title for word in [

        "stackoverflow",
        "documentation",
        "github",
        "python",
        "programming",
        "w3schools",
        "geeksforgeeks",
        "tutorial",
        "coursera",
        "udemy",
        "jupyter",
        "research paper",
        "google scholar",
        "lecture",
        "education",
        "study"

    ]):

        classification = "Productive"


    # =====================================================
    # 4. PRODUCTIVE APPLICATIONS
    # =====================================================

    elif app in [

        "code.exe",
        "pycharm64.exe",
        "devenv.exe",
        "python.exe",
        "jupyter.exe"

    ]:

        classification = "Productive"


    # =====================================================
    # 5. NEUTRAL
    # =====================================================

    else:

        classification = "Neutral"


    # =====================================================
    # SAVE CLASSIFICATION
    # =====================================================

    activity["classification"] = classification

    return activity
