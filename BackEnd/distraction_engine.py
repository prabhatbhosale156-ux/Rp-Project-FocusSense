# FocusSense - Distraction Detection Engine

activity_history = []


def analyze_distraction(application, window, duration, classification):
    """
    Analyze the current activity using previous activities.
    """

    global activity_history

    current_activity = {
        "application": application,
        "window": window,
        "duration": duration,
        "classification": classification
    }

    # Add current activity to history
    activity_history.append(current_activity)

    # Keep only the latest 20 activities
    if len(activity_history) > 20:
        activity_history.pop(0)

    result = {
        "is_distraction": False,
        "pattern": None,
        "evidence": None
    }

    # ------------------------------------------------
    # Check whether current activity is distracting
    # ------------------------------------------------

    if classification == "Distractive":

        result["is_distraction"] = True

        # Convert current activity text to lowercase
        current_text = (
            str(application).lower()
            + " "
            + str(window).lower()
        )

        # ------------------------------------------------
        # Pattern 1: Social media checking
        # ------------------------------------------------

        social_media = [
            "instagram",
            "facebook",
            "twitter",
            "x.com",
            "tiktok",
            "reddit",
            "snapchat",
            "pinterest"
        ]

        social_count = 0

        for activity in activity_history:

            activity_text = (
                str(activity["application"]).lower()
                + " "
                + str(activity["window"]).lower()
            )

            for site in social_media:

                if site in activity_text:

                    social_count += 1

                    break

        if social_count >= 2:

            result["pattern"] = (
                "Repeated social-media checking"
            )

            result["evidence"] = (
                f"Social-media activity appeared "
                f"{social_count} times in recent activity."
            )

            return result

        # ------------------------------------------------
        # Pattern 2: Gaming / Entertainment
        # ------------------------------------------------

        gaming_keywords = [
            "poki",
            "pokki",
            "gaming",
            "game",
            "games",
            "racing",
            "car racing",
            "mr racer",
            "steam",
            "twitch",
            "netflix",
            "entertainment"
        ]

        detected_keyword = None

        for keyword in gaming_keywords:

            if keyword in current_text:

                detected_keyword = keyword

                break

        if detected_keyword:

            result["pattern"] = (
                "Gaming / entertainment distraction"
            )

            result["evidence"] = (
                f"The current activity contains "
                f"the distracting entertainment keyword "
                f"'{detected_keyword}'."
            )

            return result

        # ------------------------------------------------
        # Pattern 3: YouTube / Short Videos
        # ------------------------------------------------

        video_keywords = [
            "youtube shorts",
            "youtube.com/shorts",
            "/shorts",
            "shorts"
        ]

        detected_video = None

        for keyword in video_keywords:

            if keyword in current_text:

                detected_video = keyword

                break

        if detected_video:

            result["pattern"] = (
                "Short-video distraction"
            )

            result["evidence"] = (
                "Short-form video content was detected "
                "in the current activity."
            )

            return result

        # ------------------------------------------------
        # Pattern 4: Shopping
        # ------------------------------------------------

        shopping_keywords = [
            "amazon",
            "flipkart",
            "shopping",
            "myntra"
        ]

        detected_shopping = None

        for keyword in shopping_keywords:

            if keyword in current_text:

                detected_shopping = keyword

                break

        if detected_shopping:

            result["pattern"] = (
                "Online shopping distraction"
            )

            result["evidence"] = (
                f"Online shopping activity was detected "
                f"through '{detected_shopping}'."
            )

            return result

        # ------------------------------------------------
        # Pattern 5: Frequent task switching
        # ------------------------------------------------

        if len(activity_history) >= 5:

            recent = activity_history[-5:]

            switches = 0

            for i in range(1, len(recent)):

                if (
                    recent[i]["application"]
                    != recent[i - 1]["application"]
                ):

                    switches += 1

            if switches >= 3:

                result["pattern"] = (
                    "Frequent task switching"
                )

                result["evidence"] = (
                    f"{switches} application switches "
                    f"occurred across the latest activities."
                )

                return result

        # ------------------------------------------------
        # Pattern 6: General unrelated activity
        # ------------------------------------------------

        result["pattern"] = (
            "Unrelated activity"
        )

        result["evidence"] = (
            "The current activity is unrelated "
            "to the detected study context."
        )

    return result
