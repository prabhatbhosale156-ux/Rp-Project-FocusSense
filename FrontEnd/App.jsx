import { useEffect, useState, useRef } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";

function App() {
  // =====================================================
  // AUTH STATES
  // =====================================================

  const [authReady, setAuthReady] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [userEmail, setUserEmail] = useState("");

  const [authPage, setAuthPage] = useState("login");

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const [registerUsername, setRegisterUsername] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState("");

  const [authLoading, setAuthLoading] = useState(false);
  const [authMessage, setAuthMessage] = useState("");

  // =====================================================
  // DASHBOARD STATES
  // =====================================================

  const [activity, setActivity] = useState(null);
  const [profile, setProfile] = useState(null);
  const [connected, setConnected] = useState(false);
  const [currentPage, setCurrentPage] = useState("dashboard");
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [reportHistory, setReportHistory] = useState([]);
  const [reportLoading, setReportLoading] = useState(false);
  const [studySessions, setStudySessions] = useState([]);
  const [studySessionsLoading, setStudySessionsLoading] = useState(false);

  // Full activity details for a selected completed study session.
  const [selectedStudySession, setSelectedStudySession] = useState(null);
  const [selectedSessionActivities, setSelectedSessionActivities] = useState([]);
  const [selectedSessionActivitiesLoading, setSelectedSessionActivitiesLoading] = useState(false);

  // =====================================================
  // STUDY SESSION STATES
  // =====================================================

  const [sessionActive, setSessionActive] = useState(false);
  const [sessionStarting, setSessionStarting] = useState(false);
  const [sessionEnding, setSessionEnding] = useState(false);
  // Ref lock prevents multiple End-session requests even when the user
  // clicks the button several times before React re-renders the disabled state.
  const endSessionLock = useRef(false);
  // Synchronous locks prevent duplicate requests before React state updates.
  const startSessionLock = useRef(false);
  const dataRefreshLock = useRef(false);
  const historyRefreshLock = useRef(false);
  const studySessionsRefreshLock = useRef(false);
  const [sessionStartTime, setSessionStartTime] = useState(null);
  const [sessionElapsed, setSessionElapsed] = useState(0);

  const [sessionSubject, setSessionSubject] = useState("Python");
  const [sessionGoal, setSessionGoal] = useState("Learn Functions");

  // =====================================================
  // AUTH HEADER
  // =====================================================

  const getAuthHeaders = (includeJson = false) => {
    const token = localStorage.getItem("focussense_token");
    const headers = {};

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    if (includeJson) {
      headers["Content-Type"] = "application/json";
    }

    return headers;
  };

  // =====================================================
  // HANDLE EXPIRED / INVALID AUTHENTICATION
  // =====================================================

  const handleAuthenticationFailure = () => {
    localStorage.removeItem("focussense_token");

    setIsLoggedIn(false);
    setUsername("");
    setUserEmail("");
    setActivity(null);
    setProfile(null);
    setHistory([]);
    setReportHistory([]);
    setStudySessions([]);
    setSelectedStudySession(null);
    setSelectedSessionActivities([]);
    setSelectedSessionActivitiesLoading(false);
    setSessionActive(false);
    setSessionStarting(false);
    startSessionLock.current = false;
    endSessionLock.current = false;
    setSessionEnding(false);
    dataRefreshLock.current = false;
    historyRefreshLock.current = false;
    studySessionsRefreshLock.current = false;
    setSessionStartTime(null);
    setSessionElapsed(0);
    setCurrentPage("dashboard");
    setAuthPage("login");
    setAuthMessage("Your login session expired. Please login again.");
  };

  // =====================================================
  // CHECK LOGIN SESSION
  // =====================================================

  useEffect(() => {
    const checkAuthentication = async () => {
      const token = localStorage.getItem("focussense_token");

      if (!token) {
        setIsLoggedIn(false);
        setAuthReady(true);
        return;
      }

      try {
        const response = await fetch(`${API}/me`, {
          headers: getAuthHeaders(),
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error("Authentication expired");
        }

        const data = await response.json();

        if (data.status === "success") {
          setIsLoggedIn(true);
          setUsername(data.user?.username || "");
          setUserEmail(data.user?.email || "");
        } else {
          throw new Error("Invalid authentication");
        }
      } catch (error) {
        console.error("Authentication check error:", error);
        localStorage.removeItem("focussense_token");
        setIsLoggedIn(false);
      } finally {
        setAuthReady(true);
      }
    };

    checkAuthentication();
  }, []);

  // =====================================================
  // REGISTER
  // =====================================================

  const handleRegister = async (event) => {
    event.preventDefault();
    setAuthMessage("");

    if (!registerUsername.trim() || !registerEmail.trim() || !registerPassword) {
      setAuthMessage("Please fill all fields.");
      return;
    }

    if (registerPassword !== registerConfirmPassword) {
      setAuthMessage("Passwords do not match.");
      return;
    }

    if (registerPassword.length < 6) {
      setAuthMessage("Password must be at least 6 characters.");
      return;
    }

    try {
      setAuthLoading(true);

      const response = await fetch(`${API}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: registerUsername.trim(),
          email: registerEmail.trim(),
          password: registerPassword,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Registration failed.");
      }

      if (data.status === "success") {
        setLoginEmail(registerEmail.trim());
        setLoginPassword("");
        setRegisterUsername("");
        setRegisterEmail("");
        setRegisterPassword("");
        setRegisterConfirmPassword("");
        setAuthMessage("Registration successful. Please login.");
        setAuthPage("login");
      } else {
        setAuthMessage(data.message || "Registration failed.");
      }
    } catch (error) {
      console.error("Registration error:", error);
      setAuthMessage(error.message || "Could not connect to FastAPI.");
    } finally {
      setAuthLoading(false);
    }
  };

  // =====================================================
  // LOGIN
  // =====================================================

  const handleLogin = async (event) => {
    event.preventDefault();
    setAuthMessage("");

    if (!loginEmail.trim() || !loginPassword) {
      setAuthMessage("Please enter email and password.");
      return;
    }

    try {
      setAuthLoading(true);

      const response = await fetch(`${API}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: loginEmail.trim(),
          password: loginPassword,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Login failed.");
      }

      if (data.status === "success" && data.token) {
        localStorage.setItem("focussense_token", data.token);
        setUsername(data.user?.username || data.username || "");
        setUserEmail(data.user?.email || data.email || "");
        setIsLoggedIn(true);
        setCurrentPage("dashboard");
        setLoginPassword("");
        setAuthMessage("");
      } else {
        setAuthMessage(data.message || "Invalid login response.");
      }
    } catch (error) {
      console.error("Login error:", error);
      setAuthMessage(error.message || "Could not connect to FastAPI.");
    } finally {
      setAuthLoading(false);
    }
  };

  // =====================================================
  // LOGOUT
  // =====================================================

  const handleLogout = async () => {
    try {
      await fetch(`${API}/logout`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
    } catch (error) {
      console.error("Logout request error:", error);
    }

    localStorage.removeItem("focussense_token");

    setIsLoggedIn(false);
    setUsername("");
    setUserEmail("");
    setActivity(null);
    setProfile(null);
    setHistory([]);
    setReportHistory([]);
    setStudySessions([]);
    setSessionActive(false);
    setSessionStarting(false);
    startSessionLock.current = false;
    endSessionLock.current = false;
    setSessionEnding(false);
    dataRefreshLock.current = false;
    historyRefreshLock.current = false;
    studySessionsRefreshLock.current = false;
    setSessionStartTime(null);
    setSessionElapsed(0);
    setCurrentPage("dashboard");
    setAuthPage("login");
    setAuthMessage("");
    setLoginEmail("");
    setLoginPassword("");
  };

  // =====================================================
  // GET DASHBOARD DATA
  // =====================================================

  const getData = async () => {
    if (!isLoggedIn || dataRefreshLock.current) {
      return;
    }

    // The dashboard polls every second. Do not allow a slow request to
    // overlap with the next poll and create stale/out-of-order UI updates.
    dataRefreshLock.current = true;

    try {
      // Fetch Latest Activity and Profile independently. A temporary activity
      // request failure must not prevent the live profile counters from
      // refreshing.
      try {
        const activityResponse = await fetch(
          `${API}/latest-activity`,
          {
            headers: getAuthHeaders(),
            cache: "no-store",
          }
        );

        if (activityResponse.status === 401) {
          handleAuthenticationFailure();
          return;
        }

        if (!activityResponse.ok) {
          throw new Error(`Latest activity HTTP ${activityResponse.status}`);
        }

        const activityData = await activityResponse.json();

        if (activityData.status === "success") {
          setActivity(activityData.activity);
          setConnected(true);
        }
      } catch (error) {
        console.error("Latest activity error:", error);
        setConnected(false);
      }

      try {
        const profileResponse = await fetch(
          `${API}/profile`,
          {
            headers: getAuthHeaders(),
            cache: "no-store",
          }
        );

        if (profileResponse.status === 401) {
          handleAuthenticationFailure();
          return;
        }

        if (!profileResponse.ok) {
          throw new Error(`Profile HTTP ${profileResponse.status}`);
        }

        const profileData = await profileResponse.json();

        if (profileData.status === "success" && profileData.personal_profile) {
          setProfile(profileData.personal_profile);
        }
      } catch (error) {
        console.error("Profile refresh error:", error);
      }
    } finally {
      dataRefreshLock.current = false;
    }
  };

  // =====================================================
  // ACTIVITY TIME FORMATTER
  // =====================================================

  const formatActivityTime = (value) => {
    const date = value instanceof Date ? value : new Date(value);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    const pad = (number) => String(number).padStart(2, "0");

    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
      date.getDate()
    )} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(
      date.getSeconds()
    )}`;
  };

  // =====================================================
  // DATE CONVERTER
  // =====================================================

  const getActivityDate = (item) => {
    const value =
      item?.["Start Time"] ||
      item?.start_time ||
      item?.["End Time"] ||
      item?.end_time;

    if (!value) {
      return 0;
    }

    const text = String(value).trim();

    // YYYY-MM-DD HH:mm:ss
    let match = text.match(
      /^(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?$/
    );

    if (match) {
      const year = Number(match[1]);
      const month = Number(match[2]);
      const day = Number(match[3]);
      const hour = Number(match[4]);
      const minute = Number(match[5]);
      const second = Number(match[6] || 0);

      return new Date(
        year,
        month - 1,
        day,
        hour,
        minute,
        second
      ).getTime();
    }

    // MM/DD/YYYY HH:mm:ss
    match = text.match(
      /^(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?$/
    );

    if (match) {
      const month = Number(match[1]);
      const day = Number(match[2]);
      const year = Number(match[3]);
      const hour = Number(match[4]);
      const minute = Number(match[5]);
      const second = Number(match[6] || 0);

      return new Date(
        year,
        month - 1,
        day,
        hour,
        minute,
        second
      ).getTime();
    }

    // Browser parser fallback
    const parsed = new Date(text);

    if (!isNaN(parsed.getTime())) {
      return parsed.getTime();
    }

    return 0;
  };

  // =====================================================
  // NORMALIZE CLASSIFICATION
  // =====================================================

  const normalizeClassification = (
    classification,
    application = "",
    window = ""
  ) => {
    const value = String(
      classification || ""
    )
      .trim()
      .toLowerCase();

    if (value === "productive") {
      return "Productive";
    }

    if (value === "distractive") {
      return "Distractive";
    }

    if (value === "neutral") {
      return "Neutral";
    }

    const combinedText =
      String(application) +
      " " +
      String(window);

    const text = combinedText.toLowerCase();

    // Known distracting activities
    const distractiveKeywords = [
      "pokki",
      "pokkii",
      "poki",
      "instagram",
      "facebook",
      "twitter",
      "x.com",
      "reddit",
      "tiktok",
      "snapchat",
      "pinterest",
      "netflix",
      "twitch",
      "gaming",
      "steam",
      "game",
      "youtube shorts",
      "youtube.com/shorts",
      "shorts",
      "amazon",
      "flipkart",
      "shopping",
      "meme",
      "memes",
      "entertainment"
    ];

    for (const keyword of distractiveKeywords) {
      if (text.includes(keyword)) {
        return "Distractive";
      }
    }

    return "Neutral";
  };

  // =====================================================
  // GET CLASSIFICATION FROM ACTIVITY
  // =====================================================

  const getItemClassification = (item) => {
    const application =
      item?.Application ||
      item?.application ||
      "";

    const window =
      item?.Window ||
      item?.window ||
      "";

    const classification =
      item?.Classification ||
      item?.classification ||
      "";

    return normalizeClassification(
      classification,
      application,
      window
    );
  };

  // =====================================================
  // GET ACTIVITY HISTORY
  // =====================================================

  const getHistory = async (options = {}) => {
    const force = Boolean(options.force);

    if (!isLoggedIn || (!force && historyRefreshLock.current)) {
      return;
    }

    if (force && historyRefreshLock.current) {
      for (
        let attempt = 0;
        attempt < 20 && historyRefreshLock.current;
        attempt++
      ) {
        await new Promise((resolve) => setTimeout(resolve, 50));
      }
    }

    if (historyRefreshLock.current) {
      return;
    }

    historyRefreshLock.current = true;
    setHistoryLoading(true);

    try {
      // Activity History is intentionally limited to the CURRENT study
      // session. When there is no active study session, FastAPI returns no
      // current-session activity and the page becomes empty.
      const response = await fetch(
        `${API}/activity-history`,
        { headers: getAuthHeaders(), cache: "no-store" }
      );

      if (response.status === 401) {
        handleAuthenticationFailure();
        return;
      }

      if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status}`);
      }

      const data = await response.json();

      console.log("Current Study Session Activity History:", data);

      if (
        data.status === "success" &&
        Array.isArray(data.activities)
      ) {
        const processedActivities = data.activities.map((item) => {
          const application =
            item.Application ||
            item.application ||
            "";

          const window =
            item.Window ||
            item.window ||
            "";

          const classification =
            getItemClassification(item);

          return {
            ...item,
            Classification: classification,
            Application: application,
            Window: window,
          };
        });

        processedActivities.sort(
          (a, b) =>
            getActivityDate(b) -
            getActivityDate(a)
        );

        setHistory(processedActivities);
      } else {
        setHistory([]);
      }
    } catch (error) {
      console.error(
        "Activity history error:",
        error
      );

      setHistory([]);
    } finally {
      historyRefreshLock.current = false;
      setHistoryLoading(false);
    }
  };

  // =====================================================
  // GET REPORT DATA FROM THE LATEST SAVED STUDY SESSION
  // =====================================================

  const getReportsData = async () => {
    if (!isLoggedIn) return;

    setReportLoading(true);

    try {
      const sessionsResponse = await fetch(
        `${API}/study-sessions?all=true`,
        {
          headers: getAuthHeaders(),
          cache: "no-store",
        }
      );

      if (sessionsResponse.status === 401) {
        handleAuthenticationFailure();
        return;
      }

      if (!sessionsResponse.ok) {
        throw new Error(`Study sessions HTTP ${sessionsResponse.status}`);
      }

      const sessionsData = await sessionsResponse.json();
      const sessions = Array.isArray(sessionsData?.sessions)
        ? sessionsData.sessions
        : [];

      if (sessions.length === 0) {
        return;
      }

      sessions.sort((a, b) => {
        const numA = Number(a?.session_number);
        const numB = Number(b?.session_number);

        if (Number.isFinite(numA) && Number.isFinite(numB)) {
          return numB - numA;
        }

        return `${b?.date || ""} ${b?.time || ""}`.localeCompare(
          `${a?.date || ""} ${a?.time || ""}`
        );
      });

      const latestSessionNumber = String(
        sessions[0]?.session_number ?? ""
      ).trim();

      if (!latestSessionNumber) {
        return;
      }

      // Reports need the FULL saved activity records for the latest session,
      // including Recovery Time. The /activities endpoint returns those
      // per-activity fields, while the summary endpoint may omit them.
      const activitiesResponse = await fetch(
        `${API}/study-session/${encodeURIComponent(latestSessionNumber)}/activities`,
        {
          headers: getAuthHeaders(),
          cache: "no-store",
        }
      );

      if (activitiesResponse.status === 401) {
        handleAuthenticationFailure();
        return;
      }

      if (!activitiesResponse.ok) {
        throw new Error(`Report activities HTTP ${activitiesResponse.status}`);
      }

      const activitiesData = await activitiesResponse.json();

      if (
        activitiesData.status !== "success" ||
        !Array.isArray(activitiesData.activities)
      ) {
        setReportHistory([]);
        return;
      }

      const processedActivities = activitiesData.activities.map((item) => {
        const application = item?.Application || item?.application || "";
        const window = item?.Window || item?.window || "";
        const classification = getItemClassification(item);

        return {
          ...item,
          Classification: classification,
          Application: application,
          Window: window,
        };
      });

      processedActivities.sort(
        (a, b) => getActivityDate(b) - getActivityDate(a)
      );

      if (processedActivities.length > 0) {
        setReportHistory(processedActivities);
      }
    } catch (error) {
      console.error("Reports data error:", error);
    } finally {
      setReportLoading(false);
    }
  };

  // =====================================================
  // GET STUDY SESSION HISTORY
  // =====================================================

  const getStudySessions = async () => {
    if (!isLoggedIn || studySessionsRefreshLock.current) {
      return;
    }

    studySessionsRefreshLock.current = true;
    setStudySessionsLoading(true);

    try {
      // Fetch the complete history from the CSV-backed endpoint.
      // Do NOT use a limit, slice, or pagination here.
      const csvResponse = await fetch(`${API}/study-sessions?all=true`, {
        headers: getAuthHeaders(),
        cache: "no-store",
      });

      let csvSessions = [];

      if (csvResponse.status === 401) {
        handleAuthenticationFailure();
        return;
      }

      if (csvResponse.ok) {
        const data = await csvResponse.json();

        if (data.status === "success" && Array.isArray(data.sessions)) {
          csvSessions = data.sessions;
        }
      }

      // Also read MongoDB when available. This is only a fallback/merge;
      // CSV remains the source that contains the complete history.
      let mongoSessions = [];

      try {
        const mongoResponse = await fetch(
          `${API}/mongodb-study-sessions?all=true`,
          {
            headers: getAuthHeaders(),
            cache: "no-store"
          }
        );

        if (mongoResponse.status === 401) {
          handleAuthenticationFailure();
          return;
        }

        if (mongoResponse.ok) {
          const mongoData = await mongoResponse.json();

          if (
            mongoData.status === "success" &&
            Array.isArray(mongoData.sessions)
          ) {
            mongoSessions = mongoData.sessions.map((item) => ({
              session_number: String(item.session_number ?? ""),
              subject: item.subject ?? "",
              goal: item.goal ?? "",
              duration: Number(item.duration ?? 0),
              date: item.date ?? "",
              time: item.time ?? "",
            }));
          }
        }
      } catch (mongoError) {
        console.warn("MongoDB study-session history unavailable:", mongoError);
      }

      // Merge both sources by session number. If the same session exists in
      // both places, prefer the CSV record so all CSV history is preserved.
      const merged = new Map();

      mongoSessions.forEach((session, index) => {
        const key = session.session_number || `mongo-${index}`;
        merged.set(key, session);
      });

      csvSessions.forEach((session, index) => {
        const normalized = {
          session_number: String(session.session_number ?? ""),
          subject: session.subject ?? "",
          goal: session.goal ?? "",
          duration: Number(session.duration ?? 0),
          date: session.date ?? "",
          time: session.time ?? "",
        };

        const key = normalized.session_number || `csv-${index}`;
        merged.set(key, normalized);
      });

      const allSessions = Array.from(merged.values());

      // Sort strictly by the real stored session number.
      // Highest session number must always be displayed at the top.
      // This avoids date/time formatting or duplicate timestamps changing
      // the order of the study-session history.
      allSessions.sort((a, b) => {
        const numA = Number(a.session_number);
        const numB = Number(b.session_number);

        const validA = Number.isFinite(numA);
        const validB = Number.isFinite(numB);

        if (validA && validB) {
          return numB - numA;
        }

        if (validA && !validB) {
          return -1;
        }

        if (!validA && validB) {
          return 1;
        }

        // Fallback only when a record has no numeric session number.
        const dateTimeA = `${a.date || ""} ${a.time || ""}`.trim();
        const dateTimeB = `${b.date || ""} ${b.time || ""}`.trim();
        return dateTimeB.localeCompare(dateTimeA);
      });

      console.log("ALL STUDY SESSIONS LOADED:", allSessions);
      console.log("TOTAL STUDY SESSIONS:", allSessions.length);

      setStudySessions(allSessions);
    } catch (error) {
      console.error("Study session history error:", error);
      setStudySessions([]);
    } finally {
      studySessionsRefreshLock.current = false;
      setStudySessionsLoading(false);
    }
  };


  // =====================================================
  // GET FULL ACTIVITY FOR ONE STUDY SESSION
  // =====================================================

  const getStudySessionActivities = async (session) => {
    const sessionNumber = String(session?.session_number ?? "").trim();

    if (!sessionNumber) {
      return;
    }

    // Clicking the same session again closes the activity details.
    if (selectedStudySession?.session_number === sessionNumber) {
      setSelectedStudySession(null);
      setSelectedSessionActivities([]);
      return;
    }

    setSelectedStudySession(session);
    setSelectedSessionActivities([]);
    setSelectedSessionActivitiesLoading(true);

    try {
      const response = await fetch(
        `${API}/study-session/${encodeURIComponent(sessionNumber)}/activities`,
        {
          headers: getAuthHeaders(),
          cache: "no-store",
        }
      );

      if (response.status === 401) {
        handleAuthenticationFailure();
        return;
      }

      const data = await response.json();

      if (!response.ok || data.status !== "success") {
        throw new Error(
          data.message ||
            `Could not load activities for Session ${sessionNumber}.`
        );
      }

      const activities = Array.isArray(data.activities)
        ? data.activities.map((item) => {
            const application =
              item?.Application ||
              item?.application ||
              "Unknown";

            const window =
              item?.Window ||
              item?.window ||
              "Unknown";

            const classification = getItemClassification(item);

            const durationValue =
              item?.["Duration (seconds)"] ??
              item?.duration ??
              0;

            const duration = Number(durationValue);

            // Prefer the saved Start Time / End Time. If an older activity
            // record does not contain them, reconstruct the interval from
            // its saved timestamp and duration so the table still shows
            // actual times instead of an em dash.
            let startTime =
              item?.["Start Time"] ||
              item?.start_time ||
              "";

            let endTime =
              item?.["End Time"] ||
              item?.end_time ||
              "";

            if ((!startTime || !endTime) && item?.timestamp) {
              const endDate = new Date(item.timestamp);

              if (!Number.isNaN(endDate.getTime())) {
                if (!endTime) {
                  endTime = formatActivityTime(endDate);
                }

                if (!startTime && Number.isFinite(duration)) {
                  const startDate = new Date(
                    endDate.getTime() - duration * 1000
                  );
                  startTime = formatActivityTime(startDate);
                }
              }
            }

            startTime = startTime || "—";
            endTime = endTime || "—";

            const recovery = Number(
              item?.["Recovery Time"] ??
                item?.recovery_time ??
                0
            );

            const taskSwitches = Number(
              item?.["Task Switches"] ??
                item?.task_switches ??
                0
            );

            return {
              ...item,
              Application: application,
              Window: window,
              Classification: classification,
              "Start Time": startTime,
              "End Time": endTime,
              "Duration (seconds)": Number.isFinite(duration) ? duration : 0,
              "Recovery Time": Number.isFinite(recovery) ? recovery : 0,
              "Task Switches": Number.isFinite(taskSwitches) ? taskSwitches : 0,
            };
          })
        : [];

      // Recalculate the displayed Recovery Time from the actual activity
      // timeline. Do not trust stale saved recovery values when another
      // Distractive activity occurred before the Productive return.
      const parseRecoveryActivityTime = (value) => {
        if (!value || value === "—") return null;

        let text = String(value).trim();
        if (/^\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(text)) {
          text = text.replace(/\s+/, "T");
        }

        const date = new Date(text);
        return Number.isNaN(date.getTime()) ? null : date;
      };

      const recoveryChronological = [...activities].sort(
        (a, b) =>
          getActivityDate(a) - getActivityDate(b)
      );

      let lastDistractiveEnd = null;

      recoveryChronological.forEach((item) => {
        const itemClassification = getItemClassification(item);
        const start = parseRecoveryActivityTime(item["Start Time"]);
        const end = parseRecoveryActivityTime(item["End Time"]);

        // Every new Distractive activity becomes the recovery anchor.
        // This prevents an older distraction from producing recovery time
        // after a newer distraction has already occurred.
        if (itemClassification === "Distractive") {
          item["Recovery Time"] = 0;
          lastDistractiveEnd = end;
          return;
        }

        if (itemClassification === "Productive" && lastDistractiveEnd && start) {
          const recoverySeconds =
            Math.max(0, (start.getTime() - lastDistractiveEnd.getTime()) / 1000);

          item["Recovery Time"] = Number.isFinite(recoverySeconds)
            ? recoverySeconds
            : 0;

          lastDistractiveEnd = null;
          return;
        }

        // Neutral activities do not complete recovery and do not reset the
        // current distraction anchor.
        item["Recovery Time"] = 0;
      });

      activities.sort((a, b) => getActivityDate(b) - getActivityDate(a));
      setSelectedSessionActivities(activities);
    } catch (error) {
      console.error(
        "Study session activity details error:",
        error
      );
      setSelectedSessionActivities([]);
      alert(
        error.message ||
          "Could not load the full activity for this study session."
      );
    } finally {
      setSelectedSessionActivitiesLoading(false);
    }
  };


  // =====================================================
  // INITIAL DASHBOARD
  // =====================================================

  useEffect(() => {
    if (!authReady || !isLoggedIn) {
      return;
    }

    getData();
    getStudySessions();

    const interval =
      setInterval(() => {
        getData();
      }, 1000);

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        getData();
      }
    };

    window.addEventListener("focus", getData);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      clearInterval(interval);
      window.removeEventListener("focus", getData);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [authReady, isLoggedIn]);

  // =====================================================
  // HISTORY + REPORTS AUTO REFRESH
  // =====================================================

  useEffect(() => {
    if (!authReady || !isLoggedIn) {
      return;
    }

    if (
      currentPage !== "history" &&
      currentPage !== "reports" &&
      currentPage !== "study-history"
    ) {
      return;
    }

    if (currentPage === "reports") {
      getReportsData();
    } else {
      getHistory();
    }

    if (currentPage === "study-history") {
      getStudySessions();
    }

    const interval =
      setInterval(() => {
        if (currentPage === "reports") {
          getReportsData();
        } else {
          getHistory();
        }

        if (currentPage === "study-history") {
          getStudySessions();
        }

      }, 5000);

    return () => {
      clearInterval(interval);
    };
  }, [authReady, isLoggedIn, currentPage]);

  // =====================================================
  // STUDY SESSION TIMER
  // =====================================================

  useEffect(() => {
    if (
      !sessionActive ||
      !sessionStartTime
    ) {
      return;
    }

    const timer =
      setInterval(() => {
        const elapsed = Math.floor(
          (Date.now() -
            sessionStartTime) /
            1000
        );

        setSessionElapsed(
          elapsed
        );
      }, 1000);

    return () => {
      clearInterval(timer);
    };
  }, [
    sessionActive,
    sessionStartTime
  ]);

  // =====================================================
  // FORMAT SESSION TIME
  // =====================================================

  const formatSessionTime = (
    seconds
  ) => {
    const hours = Math.floor(
      seconds / 3600
    );

    const minutes = Math.floor(
      (seconds % 3600) / 60
    );

    const secs =
      seconds % 60;

    if (hours > 0) {
      return `${String(
        hours
      ).padStart(2, "0")}:${String(
        minutes
      ).padStart(2, "0")}:${String(
        secs
      ).padStart(2, "0")}`;
    }

    return `${String(
      minutes
    ).padStart(2, "0")}:${String(
      secs
    ).padStart(2, "0")}`;
  };

  // =====================================================
  // START STUDY SESSION
  // =====================================================

  const startStudySession = async () => {
    // Block rapid double/triple clicks before React can re-render the button.
    if (
      sessionStarting ||
      sessionEnding ||
      sessionActive ||
      startSessionLock.current
    ) {
      return;
    }

    startSessionLock.current = true;

    const subject = sessionSubject.trim();
    const goal = sessionGoal.trim();

    if (!subject || !goal) {
      alert("Please enter both Subject and Study Goal.");
      return;
    }

    setSessionStarting(true);

    try {
      const response = await fetch(`${API}/start-session`, {
        method: "POST",
        headers: getAuthHeaders(true),
        body: JSON.stringify({
          subject,
          goal,
        }),
        cache: "no-store",
      });

      if (!response.ok) {
        let message = `Could not start session. HTTP ${response.status}`;
        try {
          const errorData = await response.json();
          message = errorData.detail || errorData.message || message;
        } catch (_) {
          // Keep the HTTP status message when the response is not JSON.
        }
        throw new Error(message);
      }

      const data = await response.json();

      if (data.status !== "success") {
        throw new Error(data.message || "Could not start study session.");
      }

      const startedAt =
        data.session_started_at ||
        null;

      const startedTimestamp = startedAt
        ? new Date(startedAt.replace(" ", "T")).getTime()
        : Date.now();

      setSessionStartTime(
        Number.isFinite(startedTimestamp)
          ? startedTimestamp
          : Date.now()
      );
      setSessionElapsed(0);
      // A previous completed session keeps the End-button lock set so that
      // delayed duplicate clicks cannot submit another save request. Reset it
      // when a brand-new study session starts.
      endSessionLock.current = false;
      setSessionActive(true);
      setActivity(null);
      setHistory([]);
      setReportHistory([]);
      setProfile((previous) => ({
        productive_time: 0,
        distractive_time: 0,
        productive_percentage: 0,
        neutral_time: 0,
        total_tracked_time: 0,
        total_distractions: 0,
        average_recovery_time: 0,
        task_switches: 0,
        common_distraction: "None",
        sessions: previous?.sessions || 0,
      }));

      // Immediately sync the dashboard. Subsequent polling keeps the live
      // profile counters and current activity updated automatically.
      await getData();
    } catch (error) {
      console.error("Start session error:", error);
      alert(
        error.message ||
          "Could not start study session. Make sure FastAPI is running."
      );
    } finally {
      startSessionLock.current = false;
      setSessionStarting(false);
    }
  };

  // =====================================================
  // END STUDY SESSION
  // =====================================================

  // Calculate the real recorded duration for the current study session.
  // The session duration is the wall-clock span covered by its recorded
  // activities (earliest Start Time -> latest End Time), not the React timer.
  const calculateRecordedSessionDuration = async () => {
    const fallbackDuration = sessionStartTime
      ? Math.max(
          1,
          Math.round((Date.now() - sessionStartTime) / 1000)
        )
      : Math.max(1, Number(sessionElapsed) || 1);

    try {
      const response = await fetch(`${API}/activity-history`, {
        headers: getAuthHeaders(),
        cache: "no-store",
      });

      if (!response.ok) {
        return fallbackDuration;
      }

      const data = await response.json();

      if (data.status !== "success" || !Array.isArray(data.activities)) {
        return fallbackDuration;
      }

      const latestSessionNumber = String(
        activity?.["Study Session"] ??
          activity?.study_session ??
          activity?.session_number ??
          ""
      ).trim();

      const sessionStart = Number.isFinite(sessionStartTime)
        ? sessionStartTime
        : null;

      const parseTimestamp = (value) => {
        if (!value) return null;

        let text = String(value).trim();

        // Convert the common local format into an explicit ISO-like format.
        if (/^\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(text)) {
          text = text.replace(/\s+/, "T");
        }

        const parsed = new Date(text);
        return Number.isNaN(parsed.getTime()) ? null : parsed.getTime();
      };

      let candidates = data.activities.map((item) => {
        const itemSession = String(
          item?.["Study Session"] ??
            item?.study_session ??
            item?.session_number ??
            ""
        ).trim();

        const subject = String(
          item?.["Study Subject"] ??
            item?.study_subject ??
            item?.subject ??
            ""
        ).trim();

        const goal = String(
          item?.["Study Goal"] ??
            item?.study_goal ??
            item?.goal ??
            ""
        ).trim();

        const start = parseTimestamp(
          item?.["Start Time"] ??
            item?.start_time ??
            item?.timestamp
        );

        let end = parseTimestamp(
          item?.["End Time"] ??
            item?.end_time
        );

        const duration = Number(
          item?.["Duration (seconds)"] ??
            item?.duration ??
            0
        );

        if (!end && start !== null && Number.isFinite(duration)) {
          end = start + Math.max(0, duration) * 1000;
        }

        return {
          itemSession,
          subject,
          goal,
          start,
          end,
        };
      }).filter((item) => item.start !== null && item.end !== null);

      // Prefer the exact current session number when the latest activity
      // exposes it. This prevents older sessions with the same subject/goal
      // from being included in the duration calculation.
      if (latestSessionNumber) {
        const bySession = candidates.filter(
          (item) => item.itemSession === latestSessionNumber
        );

        if (bySession.length > 0) {
          candidates = bySession;
        }
      } else if (sessionStart !== null) {
        // Fallback for older activity records that do not contain a session
        // number: use activities that belong to the current subject/goal and
        // started at or after the current session start time (with a small
        // clock tolerance).
        const subject = String(sessionSubject || "").trim();
        const goal = String(sessionGoal || "").trim();
        const filtered = candidates.filter(
          (item) =>
            item.start >= sessionStart - 5000 &&
            (!subject || item.subject === subject) &&
            (!goal || item.goal === goal)
        );

        if (filtered.length > 0) {
          candidates = filtered;
        }
      }

      if (sessionStart !== null) {
        const recent = candidates.filter(
          (item) => item.end >= sessionStart - 5000
        );

        if (recent.length > 0) {
          candidates = recent;
        }
      }

      if (candidates.length === 0) {
        return fallbackDuration;
      }

      const earliestStart = Math.min(
        ...candidates.map((item) => item.start)
      );
      const latestEnd = Math.max(
        ...candidates.map((item) => item.end)
      );

      if (!Number.isFinite(earliestStart) || !Number.isFinite(latestEnd)) {
        return fallbackDuration;
      }

      const recordedDuration = Math.round(
        (latestEnd - earliestStart) / 1000
      );

      return Math.max(1, recordedDuration);
    } catch (error) {
      console.warn(
        "Could not calculate recorded session duration; using timer fallback:",
        error
      );
      return fallbackDuration;
    }
  };

  const endStudySession = async () => {
    // Lock immediately, before any await. This prevents 3-4 rapid clicks
    // from starting multiple end-session requests while the recorded
    // duration is being calculated.
    if (!sessionActive || sessionEnding || endSessionLock.current) {
      return;
    }

    endSessionLock.current = true;
    setSessionEnding(true);

    try {
      // Use the actual recorded activity timeline for the saved session
      // duration. This prevents the history duration from becoming shorter
      // than the activities collected during the session.
      const finalDuration = await calculateRecordedSessionDuration();

      if (finalDuration <= 0) {
        throw new Error(
          "Please run the study session for at least a few seconds."
        );
      }

      const response = await fetch(`${API}/study-session`, {
        method: "POST",
        headers: getAuthHeaders(true),
        body: JSON.stringify({
          subject: sessionSubject,
          goal: sessionGoal,
          duration: finalDuration,
        }),
        cache: "no-store",
      });

      let data = {};

      try {
        data = await response.json();
      } catch (parseError) {
        data = {};
      }

      if (!response.ok || data.status !== "success") {
        throw new Error(
          data.message ||
            `Could not end study session. HTTP ${response.status}`
        );
      }

      setSessionActive(false);
      setSessionEnding(false);
      setSessionStartTime(null);
      setSessionElapsed(0);

      await getData();
      await getHistory({ force: true });
      await getStudySessions();

      alert(
        `Study session completed!\n\nSubject: ${sessionSubject}\nGoal: ${sessionGoal}\nSession Duration: ${formatSessionTime(finalDuration)}\n\nSession saved successfully.`
      );
    } catch (error) {
      console.error("End session error:", error);

      // Release the lock only when saving fails so the user can try again.
      // After a successful save, the next Start Session resets the lock.
      endSessionLock.current = false;
      setSessionEnding(false);

      alert(
        error.message ||
          "Could not save the study session. Please try ending it again."
      );
    }
  };

  // =====================================================
  // CLEAR HISTORY
  // =====================================================

  const clearHistory =
    async () => {
      const confirmClear =
        window.confirm(
          "Are you sure you want to clear all activity history?"
        );

      if (!confirmClear) {
        return;
      }

      try {
        const response =
          await fetch(
            `${API}/activity-history`,
            {
              method: "DELETE",
              headers: getAuthHeaders(),
            }
          );

        if (response.status === 401) {
          handleAuthenticationFailure();
          return;
        }

        const data =
          await response.json();

        if (
          data.status ===
          "success"
        ) {
          setHistory([]);
          setReportHistory([]);
          setActivity(null);

          alert(
            "Activity history cleared successfully."
          );
        } else {
          alert(
            "Unable to clear activity history."
          );
        }
      } catch (error) {
        console.error(
          "Clear history error:",
          error
        );

        alert(
          "Could not connect to backend."
        );
      }
    };

  // =====================================================
  // CURRENT ACTIVITY CLASSIFICATION
  // =====================================================

  const classification =
    activity
      ? normalizeClassification(
          activity.classification,
          activity.application,
          activity.window
        )
      : "No Activity";

  // =====================================================
  // CLASSIFICATION CSS
  // =====================================================

  const getClassificationClass =
    (value) => {
      const normalized =
        String(value || "")
          .toLowerCase();

      if (
        normalized ===
        "productive"
      ) {
        return "classification productive";
      }

      if (
        normalized ===
        "distractive"
      ) {
        return "classification distractive";
      }

      return "classification neutral";
    };

  // =====================================================
  // LOGIN PAGE
  // =====================================================

  const renderLoginPage = () => {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #eef2ff, #f8fafc)",
          padding: "20px",
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: "430px",
            background: "#ffffff",
            borderRadius: "20px",
            padding: "35px",
            boxShadow: "0 20px 50px rgba(0,0,0,0.12)",
          }}
        >
          <div style={{ textAlign: "center", marginBottom: "28px" }}>
            <div style={{ fontSize: "52px", marginBottom: "8px" }}>🧠</div>
            <h1 style={{ margin: 0 }}>FocusSense</h1>
            <p style={{ marginTop: "8px", color: "#64748b" }}>Study Intelligence</p>
          </div>

          <form onSubmit={handleLogin}>
            <label style={{ display: "block", marginBottom: "7px", fontWeight: "600" }}>Email</label>
            <input
              type="email"
              value={loginEmail}
              onChange={(e) => setLoginEmail(e.target.value)}
              placeholder="Enter your email"
              autoComplete="email"
              style={{ width: "100%", boxSizing: "border-box", padding: "13px", marginBottom: "16px", border: "1px solid #cbd5e1", borderRadius: "10px", fontSize: "15px" }}
            />

            <label style={{ display: "block", marginBottom: "7px", fontWeight: "600" }}>Password</label>
            <input
              type="password"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password"
              style={{ width: "100%", boxSizing: "border-box", padding: "13px", marginBottom: "18px", border: "1px solid #cbd5e1", borderRadius: "10px", fontSize: "15px" }}
            />

            {authMessage && (
              <div
                style={{
                  padding: "11px",
                  marginBottom: "16px",
                  borderRadius: "9px",
                  background: authMessage.includes("successful") ? "#dcfce7" : "#fee2e2",
                  color: authMessage.includes("successful") ? "#166534" : "#991b1b",
                  fontSize: "14px",
                }}
              >
                {authMessage}
              </div>
            )}

            <button type="submit" disabled={authLoading} style={{ width: "100%", padding: "13px", border: "none", borderRadius: "10px", background: "#4f46e5", color: "#ffffff", fontSize: "16px", fontWeight: "600", cursor: authLoading ? "not-allowed" : "pointer" }}>
              {authLoading ? "Logging in..." : "Login"}
            </button>
          </form>

          <div style={{ textAlign: "center", marginTop: "22px", color: "#64748b" }}>
            Don't have an account?
            <button
              type="button"
              onClick={() => { setAuthPage("register"); setAuthMessage(""); }}
              style={{ marginLeft: "5px", border: "none", background: "transparent", color: "#4f46e5", fontWeight: "600", cursor: "pointer" }}
            >Register</button>
          </div>
        </div>
      </div>
    );
  };

  // =====================================================
  // REGISTER PAGE
  // =====================================================

  const renderRegisterPage = () => {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #eef2ff, #f8fafc)",
          padding: "20px",
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: "430px",
            background: "#ffffff",
            borderRadius: "20px",
            padding: "35px",
            boxShadow: "0 20px 50px rgba(0,0,0,0.12)",
          }}
        >
          <div style={{ textAlign: "center", marginBottom: "25px" }}>
            <div style={{ fontSize: "52px", marginBottom: "8px" }}>🧠</div>
            <h1 style={{ margin: 0 }}>Create Account</h1>
            <p style={{ marginTop: "8px", color: "#64748b" }}>Join FocusSense</p>
          </div>

          <form onSubmit={handleRegister}>
            <label style={{ display: "block", marginBottom: "7px", fontWeight: "600" }}>Username</label>
            <input type="text" value={registerUsername} onChange={(e) => setRegisterUsername(e.target.value)} placeholder="Enter username" autoComplete="username" style={{ width: "100%", boxSizing: "border-box", padding: "13px", marginBottom: "15px", border: "1px solid #cbd5e1", borderRadius: "10px", fontSize: "15px" }} />

            <label style={{ display: "block", marginBottom: "7px", fontWeight: "600" }}>Email</label>
            <input type="email" value={registerEmail} onChange={(e) => setRegisterEmail(e.target.value)} placeholder="Enter email" autoComplete="email" style={{ width: "100%", boxSizing: "border-box", padding: "13px", marginBottom: "15px", border: "1px solid #cbd5e1", borderRadius: "10px", fontSize: "15px" }} />

            <label style={{ display: "block", marginBottom: "7px", fontWeight: "600" }}>Password</label>
            <input type="password" value={registerPassword} onChange={(e) => setRegisterPassword(e.target.value)} placeholder="Minimum 6 characters" autoComplete="new-password" style={{ width: "100%", boxSizing: "border-box", padding: "13px", marginBottom: "15px", border: "1px solid #cbd5e1", borderRadius: "10px", fontSize: "15px" }} />

            <label style={{ display: "block", marginBottom: "7px", fontWeight: "600" }}>Confirm Password</label>
            <input type="password" value={registerConfirmPassword} onChange={(e) => setRegisterConfirmPassword(e.target.value)} placeholder="Confirm password" autoComplete="new-password" style={{ width: "100%", boxSizing: "border-box", padding: "13px", marginBottom: "18px", border: "1px solid #cbd5e1", borderRadius: "10px", fontSize: "15px" }} />

            {authMessage && (
              <div style={{ padding: "11px", marginBottom: "16px", borderRadius: "9px", background: authMessage.includes("successful") ? "#dcfce7" : "#fee2e2", color: authMessage.includes("successful") ? "#166534" : "#991b1b", fontSize: "14px" }}>
                {authMessage}
              </div>
            )}

            <button type="submit" disabled={authLoading} style={{ width: "100%", padding: "13px", border: "none", borderRadius: "10px", background: "#4f46e5", color: "#ffffff", fontSize: "16px", fontWeight: "600", cursor: authLoading ? "not-allowed" : "pointer" }}>
              {authLoading ? "Creating Account..." : "Register"}
            </button>
          </form>

          <div style={{ textAlign: "center", marginTop: "22px", color: "#64748b" }}>
            Already have an account?
            <button type="button" onClick={() => { setAuthPage("login"); setAuthMessage(""); }} style={{ marginLeft: "5px", border: "none", background: "transparent", color: "#4f46e5", fontWeight: "600", cursor: "pointer" }}>Login</button>
          </div>
        </div>
      </div>
    );
  };

  // =====================================================
  // RECOVERY CALCULATION
  // =====================================================

  // Recovery is measured only from the MOST RECENT Distractive activity
  // before a Productive return. Neutral activities do not replace that
  // pending distraction. A newer Distractive activity always replaces the
  // older one, so an older distraction can never create a false recovery.
  const calculateAverageRecovery = (activities, sessionNumber = null) => {
    if (!Array.isArray(activities) || activities.length === 0) {
      return 0;
    }

    const normalizedSession =
      sessionNumber === null || sessionNumber === undefined
        ? null
        : String(sessionNumber).trim();

    const sessionActivities = activities.filter((item) => {
      if (normalizedSession === null || normalizedSession === "") {
        return true;
      }

      const itemSession = String(
        item?.["Study Session"] ??
          item?.study_session ??
          item?.session_number ??
          ""
      ).trim();

      return itemSession === normalizedSession;
    });

    const parseRecoveryDate = (value) => {
      if (!value || value === "—") return null;

      let text = String(value).trim();
      if (
        /^\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(
          text
        )
      ) {
        text = text.replace(/\s+/, "T");
      }

      const parsed = new Date(text);
      return Number.isNaN(parsed.getTime()) ? null : parsed;
    };

    const chronological = [...sessionActivities]
      .map((item, originalIndex) => ({
        item,
        originalIndex,
        start: parseRecoveryDate(
          item?.["Start Time"] ?? item?.start_time ?? item?.timestamp
        ),
        end: parseRecoveryDate(
          item?.["End Time"] ?? item?.end_time
        ),
      }))
      .filter((entry) => entry.start !== null)
      .sort((a, b) => {
        const startDifference =
          a.start.getTime() - b.start.getTime();
        return startDifference !== 0
          ? startDifference
          : a.originalIndex - b.originalIndex;
      });

    const recoverySamples = [];

    chronological.forEach((entry, index) => {
      if (getItemClassification(entry.item) !== "Productive") {
        return;
      }

      // Walk backwards only through Neutral activities. The first non-neutral
      // activity immediately before this Productive activity is the only one
      // allowed to determine recovery. Therefore a newer distraction always
      // wins over an older distraction.
      let previousIndex = index - 1;
      while (
        previousIndex >= 0 &&
        getItemClassification(chronological[previousIndex].item) === "Neutral"
      ) {
        previousIndex -= 1;
      }

      if (previousIndex < 0) {
        return;
      }

      const previousEntry = chronological[previousIndex];
      if (
        getItemClassification(previousEntry.item) !== "Distractive" ||
        !previousEntry.end
      ) {
        return;
      }

      const recoverySeconds =
        (entry.start.getTime() - previousEntry.end.getTime()) / 1000;

      if (recoverySeconds >= 0 && recoverySeconds <= 3600) {
        // Include zero-second completed recoveries. They are real recovery
        // events and must not be replaced by an older distraction's gap.
        recoverySamples.push(recoverySeconds);
      }
    });

    return recoverySamples.length > 0
      ? recoverySamples.reduce((sum, value) => sum + value, 0) /
          recoverySamples.length
      : 0;
  };

  // =====================================================
  // DASHBOARD PAGE
  // =====================================================

  const DashboardPage =
    () => {
      const currentSessionNumber = sessionActive
        ? String(
            activity?.["Study Session"] ??
              activity?.study_session ??
              activity?.session_number ??
              ""
          ).trim()
        : "";

      const dashboardRecovery = sessionActive
        ? calculateAverageRecovery(history, currentSessionNumber)
        : 0;

      // Focus Fingerprint uses the recovery calculated directly from
      // recorded activity timestamps, rather than the cached profile value.
      const fingerprintRecovery = calculateAverageRecovery(history);

      return (
        <>
          {/* SESSION */}

          <section className="session-card">
            <div>
              <small>
                CURRENT STUDY SESSION
              </small>

              <h2>
                {sessionActive
                  ? `${sessionSubject} — ${sessionGoal}`
                  : "Python — Learn Functions"}
              </h2>

              <div className="session-info">
                📚 Subject:{" "}
                {sessionSubject}
                &nbsp;&nbsp;

                🎯 Goal:{" "}
                {sessionGoal}
                &nbsp;&nbsp;

                ⏱ Duration:{" "}
                {sessionActive
                  ? formatSessionTime(
                      sessionElapsed
                    )
                  : "60 min"}
              </div>
            </div>
          </section>

          {/* STATS */}

          <section className="stats">

            {/* PRODUCTIVE */}

            <div className="stat-card">
              <div className="stat-icon green">
                ✓
              </div>

              <div>
                <p>
                  Productive Time
                </p>

                <h2>
                  {profile
                    ? `${Math.round(
                        profile.productive_time ||
                          0
                      )} sec`
                    : "0 sec"}
                </h2>
              </div>
            </div>

            {/* DISTRACTIVE */}

            <div className="stat-card">
              <div className="stat-icon red">
                !
              </div>

              <div>
                <p>
                  Distractive Time
                </p>

                <h2>
                  {profile
                    ? `${Math.round(
                        profile.distractive_time ||
                          0
                      )} sec`
                    : "0 sec"}
                </h2>

                <small>
                  {profile?.total_distractions ||
                    0}{" "}
                  distractions
                </small>
              </div>
            </div>

            {/* RECOVERY */}

            <div className="stat-card">
              <div className="stat-icon blue">
                ↻
              </div>

              <div>
                <p>
                  Recovery Time
                </p>

                <h2>
                  {`${Math.round(
                    dashboardRecovery
                  )} sec`}
                </h2>
              </div>
            </div>

            {/* FOCUS SCORE */}

            <div className="stat-card">
              <div className="stat-icon purple">
                ★
              </div>

              <div>
                <p>
                  Focus Score
                </p>

                <h2>
                  {profile
                    ? Math.round(
                        profile.productive_percentage ||
                          0
                      )
                    : 0}

                  <span>
                    /100
                  </span>
                </h2>

                <small>
                  {profile?.productive_percentage >=
                  80
                    ? "Excellent"
                    : "Needs Improvement"}
                </small>
              </div>
            </div>
          </section>

          {/* MAIN CONTENT */}

          <section className="content-grid">

            {/* LATEST ACTIVITY */}

            <div className="panel activity-panel">

              <div className="panel-title">

                <div>
                  <h2>
                    Latest Activity
                  </h2>

                  <p>
                    Real-time activity detected by FocusSense
                  </p>
                </div>

                <span className="live-badge">
                  LIVE
                </span>

              </div>

              {!activity ? (
                <div className="empty">
                  Waiting for activity...
                </div>
              ) : (
                <div className="latest-activity">

                  <h3>
                    🖥{" "}
                    {activity.application}
                  </h3>

                  <p>
                    <b>
                      Window:
                    </b>{" "}
                    {activity.window}
                  </p>

                  <p>
                    <b>
                      Duration:
                    </b>{" "}
                    {Number(
                      activity.duration ||
                        0
                    ).toFixed(2)}{" "}
                    seconds
                  </p>

                  <div
                    className={getClassificationClass(
                      classification
                    )}
                  >
                    {classification}
                  </div>

                  {(activity?.live_only === true || activity?.recorded === false) && (
                    <div
                      style={{
                        marginTop: "10px",
                        padding: "8px 10px",
                        borderRadius: "8px",
                        background: "#fef3c7",
                        color: "#92400e",
                        fontWeight: "600",
                        fontSize: "13px",
                      }}
                    >
                      
                    </div>
                  )}

                  {classification ===
                    "Distractive" && (
                    <div className="analysis-box">

                      <span>
                        ⚠ Distraction Detected
                      </span>

                      <h3>
                        {activity
                          ?.distraction
                          ?.pattern ||
                          "Known distracting activity"}
                      </h3>

                      <p>
                        {activity
                          ?.distraction
                          ?.evidence ||
                          activity.window}
                      </p>

                    </div>
                  )}
                </div>
              )}
            </div>

            {/* DISTRACTION ANALYSIS */}

            <div className="panel distraction-panel">

              <div className="panel-title">

                <div>
                  <h2>
                    Why Was I Distracted?
                  </h2>

                  <p>
                    Behavioral pattern analysis
                  </p>
                </div>

                <span className="question">
                  ?
                </span>

              </div>

              <div className="analysis-box">

                <span>
                  Possible Pattern
                </span>

                <h3>
                  {activity
                    ?.distraction
                    ?.pattern ||
                    (classification ===
                    "Distractive"
                      ? "Known distracting activity"
                      : "No distraction detected")}
                </h3>

                <span>
                  Evidence
                </span>

                <p>
                  {activity
                    ?.distraction
                    ?.evidence ||
                    (classification ===
                    "Distractive"
                      ? activity.window
                      : "No distraction evidence available.")}
                </p>

              </div>
            </div>
          </section>

          {/* BOTTOM GRID */}

          <section className="bottom-grid">

            {/* FOCUS FINGERPRINT */}

            <div className="panel">

              <h2>
                🧠 Focus Fingerprint
              </h2>

              <div className="fingerprint-grid">

                <div>
                  <span>
                    Productive Activity
                  </span>

                  <strong>
                    {profile
                      ? `${Math.round(
                          profile.productive_percentage ||
                            0
                        )}%`
                      : "0%"}
                  </strong>
                </div>

                <div>
                  <span>
                    Distractions / Session
                  </span>

                  <strong>
                    {profile?.total_distractions ||
                      0}
                  </strong>
                </div>

                <div>
                  <span>
                    Average Recovery
                  </span>

                  <strong>
                    {`${Math.round(
                      fingerprintRecovery || 0
                    )} sec`}
                  </strong>
                </div>

                <div>
                  <span>
                    Task Switches
                  </span>

                  <strong>
                    {profile?.task_switches ||
                      0}
                  </strong>
                </div>

                <div>
                  <span>
                    Common Distraction
                  </span>

                  <strong>
                    {profile?.common_distraction ||
                      "None"}
                  </strong>
                </div>

              </div>
            </div>

            {/* LATEST RESULT */}

            <div className="panel result-panel">

              <h2>
                🔍 Latest Activity
              </h2>

              {!activity ? (
                <p className="empty">
                  Waiting for collector...
                </p>
              ) : (
                <>
                  <p>
                    <b>
                      Application:
                    </b>{" "}
                    {activity.application}
                  </p>

                  <p>
                    <b>
                      Window:
                    </b>{" "}
                    {activity.window}
                  </p>

                  <p>
                    <b>
                      Duration:
                    </b>{" "}
                    {Number(
                      activity.duration ||
                        0
                    ).toFixed(2)}{" "}
                    seconds
                  </p>

                  <div
                    className={getClassificationClass(
                      classification
                    )}
                  >
                    {classification}
                  </div>
                </>
              )}

            </div>
          </section>
        </>
      );
    };

  // =====================================================
  // STUDY SESSION PAGE
  // =====================================================

  const renderStudySessionPage =() => {

      const productiveTime =
        profile?.productive_time ||
        0;

      const distractiveTime =
        profile?.distractive_time ||
        0;

      const focusScore =
        Math.round(
          profile?.productive_percentage ||
            0
        );

      return (
        <section className="study-session-page">

          {/* SESSION CONTROL */}

          <div className="panel session-control-panel">

            <div className="panel-title">

              <div>
                <h2>
                  🎯 Study Session
                </h2>

                <p>
                  Start and monitor your focused study session
                </p>
              </div>

              <span
                className={
                  sessionActive
                    ? "live-badge"
                    : "classification neutral"
                }
              >
                {sessionActive
                  ? "SESSION ACTIVE"
                  : "SESSION READY"}
              </span>

            </div>

            {/* TIMER */}

            <div className="session-timer">

              <span>
                {formatSessionTime(
                  sessionElapsed
                )}
              </span>

              <small>
                {sessionActive
                  ? "Study session in progress"
                  : "Session duration"}
              </small>

            </div>

            {/* SESSION DETAILS */}

            <div className="session-form">

              <div>
                <label>
                  Subject
                </label>

                <input
                  type="text"
                  value={
                    sessionSubject
                  }
                  onChange={(e) =>
                    setSessionSubject(
                      e.target.value
                    )
                  }
                  disabled={
                    sessionActive
                  }
                  placeholder="Enter subject"
                />
              </div>

              <div>
                <label>
                  Study Goal
                </label>

                <input
                  type="text"
                  value={
                    sessionGoal
                  }
                  onChange={(e) =>
                    setSessionGoal(
                      e.target.value
                    )
                  }
                  disabled={
                    sessionActive
                  }
                  placeholder="Enter study goal"
                />
              </div>

            </div>

            {/* BUTTON */}

            <div className="session-actions">

              {!sessionActive ? (

                <button
                  className="start-session-button"
                  onClick={
                    startStudySession
                  }
                  disabled={sessionStarting}
                  style={{
                    opacity: sessionStarting ? 0.7 : 1,
                    cursor: sessionStarting ? "wait" : "pointer",
                  }}
                >
                  {sessionStarting
                    ? "⏳ Starting Study Session..."
                    : "▶️ Start Study Session"}
                </button>

              ) : (

                <button
                  className="end-session-button"
                  onClick={
                    endStudySession
                  }
                  disabled={sessionEnding}
                  style={{
                    opacity: sessionEnding ? 0.7 : 1,
                    cursor: sessionEnding ? "wait" : "pointer",
                  }}
                >
                  {sessionEnding
                    ? "⏳ Ending Study Session..."
                    : "⏹️ End Study Session"}
                </button>

              )}

            </div>

          </div>

          {/* SESSION STATISTICS */}

          <section className="stats">

            {/* PRODUCTIVE */}

            <div className="stat-card">

              <div className="stat-icon green">
                ✓
              </div>

              <div>
                <p>
                  Productive Time
                </p>

                <h2>
                  {Math.round(
                    productiveTime
                  )}{" "}
                  sec
                </h2>
              </div>

            </div>

            {/* DISTRACTIVE */}

            <div className="stat-card">

              <div className="stat-icon red">
                !
              </div>

              <div>
                <p>
                  Distractive Time
                </p>

                <h2>
                  {Math.round(
                    distractiveTime
                  )}{" "}
                  sec
                </h2>
              </div>

            </div>

            {/* FOCUS SCORE */}

            <div className="stat-card">

              <div className="stat-icon purple">
                ★
              </div>

              <div>
                <p>
                  Focus Score
                </p>

                <h2>
                  {focusScore}
                  <span>
                    /100
                  </span>
                </h2>
              </div>

            </div>

            {/* DISTRACTIONS */}

            <div className="stat-card">

              <div className="stat-icon blue">
                ⚠
              </div>

              <div>
                <p>
                  Distractions
                </p>

                <h2>
                  {profile?.total_distractions ||
                    0}
                </h2>
              </div>

            </div>

          </section>

          {/* SESSION INFORMATION */}

          <section className="content-grid">

            {/* CURRENT SESSION */}

            <div className="panel">

              <h2>
                📚 Current Study Session
              </h2>

              <div className="session-details">

                <div>
                  <span>
                    Subject
                  </span>

                  <strong>
                    {sessionSubject}
                  </strong>
                </div>

                <div>
                  <span>
                    Goal
                  </span>

                  <strong>
                    {sessionGoal}
                  </strong>
                </div>

                <div>
                  <span>
                    Status
                  </span>

                  <strong>
                    {sessionActive
                      ? "Active"
                      : "Not Started"}
                  </strong>
                </div>

                <div>
                  <span>
                    Duration
                  </span>

                  <strong>
                    {formatSessionTime(
                      sessionElapsed
                    )}
                  </strong>
                </div>

              </div>

            </div>

            {/* LIVE ACTIVITY */}

            <div className="panel">

              <div className="panel-title">

                <div>
                  <h2>
                    🖥 Live Activity
                  </h2>

                  <p>
                    Activity detected during your study session
                  </p>
                </div>

                <span className="live-badge">
                  LIVE
                </span>

              </div>

              {!activity ? (

                <div className="empty">
                  Waiting for activity...
                </div>

              ) : (

                <div className="latest-activity">

                  <h3>
                    🖥{" "}
                    {activity.application}
                  </h3>

                  <p>
                    <b>
                      Window:
                    </b>{" "}
                    {activity.window}
                  </p>

                  <p>
                    <b>
                      Duration:
                    </b>{" "}
                    {Number(
                      activity.duration ||
                        0
                    ).toFixed(2)}{" "}
                    seconds
                  </p>

                  <div
                    className={getClassificationClass(
                      classification
                    )}
                  >
                    {classification}
                  </div>

                </div>

              )}

            </div>

          </section>

          {/* RECOMMENDATION */}

          <div className="panel">

            <h2>
              💡 Study Recommendation
            </h2>

            <div className="focus-recommendation">

              <strong>
                {focusScore >= 80
                  ? "Excellent Focus"
                  : focusScore >= 60
                  ? "Good Focus"
                  : "Focus Needs Improvement"}
              </strong>

              <p>
                {focusScore >= 80
                  ? "You are maintaining strong productivity. Continue your current study routine."
                  : focusScore >= 60
                  ? "Your productivity is good. Try reducing distractions to improve your focus."
                  : "Try closing distracting websites and applications while studying."}
              </p>

            </div>

          </div>

        </section>
      );
    };

  // =====================================================
  // STUDY SESSION HISTORY PAGE
  // =====================================================

  const StudySessionHistoryPage = () => {
    return (
      <section className="history-page">
        <div className="panel history-panel">
          <div className="panel-title">
            <div>
              <h2>📚 Study Session History</h2>
              <p>Completed study sessions recorded by FocusSense</p>
            </div>

            <button
              className="refresh-button"
              onClick={getStudySessions}
              disabled={studySessionsLoading}
            >
              {studySessionsLoading ? "Loading..." : "↻ Refresh"}
            </button>
          </div>

          <div className="history-summary">
            Total Study Sessions:{" "}
            <strong>{studySessions.length}</strong>
          </div>

          {studySessionsLoading && studySessions.length === 0 ? (
            <div className="empty">Loading study sessions...</div>
          ) : studySessions.length === 0 ? (
            <div className="empty">
              No study sessions found.
              <br />
              Start a study session to create your first record.
            </div>
          ) : (
            <>
              <div className="history-table-container">
                <table className="history-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Subject</th>
                      <th>Goal</th>
                      <th>Duration</th>
                      <th>Date</th>
                      <th>Time</th>
                      <th>Activity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {studySessions.map((session, index) => {
                      const duration = Number(session.duration || 0);
                      const sessionNumber = String(
                        session.session_number ?? ""
                      );
                      // Visible numbering is continuous and follows the
                      // displayed order: highest number/latest session on top,
                      // lowest number/oldest session at the bottom.
                      // The real session_number is kept internally for View Activity.
                      const displaySessionNumber = studySessions.length - index;
                      const isSelected =
                        selectedStudySession?.session_number ===
                        sessionNumber;

                      return (
                        <tr
                          key={
                            sessionNumber ||
                            `${index}-${session.date}-${session.time}`
                          }
                        >
                          <td><b>{displaySessionNumber}</b></td>
                          <td>📚 <b>{session.subject}</b></td>
                          <td>{session.goal}</td>
                          <td>
                            {isNaN(duration)
                              ? "0.00"
                              : duration.toFixed(2)} sec
                          </td>
                          <td>{session.date || "—"}</td>
                          <td>{session.time || "—"}</td>
                          <td>
                            <button
                              className="refresh-button"
                              onClick={() =>
                                getStudySessionActivities({
                                  ...session,
                                  display_session_number: displaySessionNumber,
                                })
                              }
                              disabled={
                                selectedSessionActivitiesLoading &&
                                isSelected
                              }
                              style={{
                                whiteSpace: "nowrap",
                                minWidth: "130px",
                              }}
                            >
                              {selectedSessionActivitiesLoading && isSelected
                                ? "Loading..."
                                : isSelected
                                ? "▲ Hide Activity"
                                : "🔍 View Activity"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {selectedStudySession && (
                <div
                  className="panel"
                  style={{
                    marginTop: "20px",
                    border: "1px solid #dbeafe",
                  }}
                >
                  <div className="panel-title">
                    <div>
                      <h2>
                        🖥 Full Activity — Session {
                          selectedStudySession.display_session_number ??
                          selectedStudySession.session_number
                        }
                      </h2>
                      <p>
                        {selectedStudySession.subject || "—"} • {selectedStudySession.goal || "—"}
                      </p>
                    </div>

                    <span className="live-badge">
                      {selectedSessionActivities.length} ACTIVITIES
                    </span>
                  </div>

                  {selectedSessionActivitiesLoading ? (
                    <div className="empty">Loading full session activity...</div>
                  ) : selectedSessionActivities.length === 0 ? (
                    <div className="empty">
                      No recorded activity was found for this study session.
                    </div>
                  ) : (
                    <div className="history-table-container">
                      <table className="history-table">
                        <thead>
                          <tr>
                            <th>#</th>
                            <th>Application</th>
                            <th>Window</th>
                            <th>Start Time</th>
                            <th>End Time</th>
                            <th>Duration</th>
                            <th>Classification</th>
                            <th>Recovery</th>
                            <th>Task Switches</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedSessionActivities.map((item, index) => {
                            const duration = Number(
                              item?.["Duration (seconds)"] ??
                                item?.duration ??
                                0
                            );

                            const taskSwitches = Number(
                              item?.["Task Switches"] ??
                                item?.task_switches ??
                                0
                            );

                            // Recalculate Recovery from the actual chronological
                            // activity sequence. Only the nearest non-neutral
                            // activity before a Productive return can define
                            // recovery, so a newer distraction always replaces
                            // any older distraction.
                            let recovery = 0;

                            const itemClassification =
                              getItemClassification(item);

                            if (itemClassification === "Productive") {
                              const parseRecoveryDate = (value) => {
                                if (!value || value === "—") return null;

                                let text = String(value).trim();
                                if (
                                  /^\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(
                                    text
                                  )
                                ) {
                                  text = text.replace(/\s+/, "T");
                                }

                                const parsed = new Date(text);
                                return Number.isNaN(parsed.getTime())
                                  ? null
                                  : parsed;
                              };

                              const orderedActivities =
                                selectedSessionActivities
                                  .map((activityItem, activityIndex) => ({
                                    activityItem,
                                    activityIndex,
                                    start: parseRecoveryDate(
                                      activityItem?.["Start Time"] ??
                                        activityItem?.start_time ??
                                        activityItem?.timestamp
                                    ),
                                    end: parseRecoveryDate(
                                      activityItem?.["End Time"] ??
                                        activityItem?.end_time
                                    ),
                                  }))
                                  .filter((entry) => entry.start !== null)
                                  .sort((a, b) => {
                                    const diff =
                                      a.start.getTime() - b.start.getTime();
                                    return diff !== 0
                                      ? diff
                                      : a.activityIndex - b.activityIndex;
                                  });

                              const currentIndex =
                                orderedActivities.findIndex(
                                  (entry) => entry.activityItem === item
                                );

                              if (currentIndex > 0) {
                                let previousIndex = currentIndex - 1;

                                // Neutral activities represent time between a
                                // distraction and the eventual return to work.
                                // Keep walking backward until the nearest
                                // non-neutral activity is found.
                                while (
                                  previousIndex >= 0 &&
                                  getItemClassification(
                                    orderedActivities[previousIndex].activityItem
                                  ) === "Neutral"
                                ) {
                                  previousIndex -= 1;
                                }

                                if (previousIndex >= 0) {
                                  const previousEntry =
                                    orderedActivities[previousIndex];

                                  if (
                                    getItemClassification(
                                      previousEntry.activityItem
                                    ) === "Distractive" &&
                                    previousEntry.end &&
                                    orderedActivities[currentIndex].start
                                  ) {
                                    const calculatedRecovery =
                                      (orderedActivities[currentIndex].start.getTime() -
                                        previousEntry.end.getTime()) /
                                      1000;

                                    if (
                                      calculatedRecovery >= 0 &&
                                      calculatedRecovery <= 3600
                                    ) {
                                      recovery = calculatedRecovery;
                                    }
                                  }
                                }
                              }
                            }

                            return (
                              <tr
                                key={`${index}-${
                                  item?.["Start Time"] ||
                                  item?.start_time ||
                                  ""
                                }-${item?.Application || item?.application || ""}`}
                              >
                                <td><b>{selectedSessionActivities.length - index}</b></td>
                                <td>
                                  <b>
                                    {item?.Application ||
                                      item?.application ||
                                      "Unknown"}
                                  </b>
                                </td>
                                <td className="window-cell">
                                  {item?.Window ||
                                    item?.window ||
                                    "Unknown"}
                                </td>
                                <td>
                                  {item?.["Start Time"] ||
                                    item?.start_time ||
                                    "—"}
                                </td>
                                <td>
                                  {item?.["End Time"] ||
                                    item?.end_time ||
                                    "—"}
                                </td>
                                <td>
                                  {Number.isFinite(duration)
                                    ? duration.toFixed(2)
                                    : "0.00"} sec
                                </td>
                                <td>
                                  <span
                                    className={getClassificationClass(
                                      itemClassification
                                    )}
                                  >
                                    {itemClassification}
                                  </span>
                                </td>
                                <td>
                                  {Number.isFinite(recovery)
                                    ? recovery.toFixed(2)
                                    : "0.00"} sec
                                </td>
                                <td>
                                  {Number.isFinite(taskSwitches)
                                    ? taskSwitches
                                    : 0}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </section>
    );
  };

  // =====================================================
  // ACTIVITY HISTORY PAGE
  // =====================================================

  const ActivityHistoryPage =
    () => {
      return (
        <section className="history-page">

          <div className="panel history-panel">

            {/* HEADER */}

            <div className="panel-title">

              <div>
                <h2>
                  🕒 Activity History
                </h2>

                <p>
                  Complete activity collected by FocusSense
                </p>
              </div>

              <div className="history-buttons">

                <button
                  className="refresh-button"
                  onClick={
                    getHistory
                  }
                  disabled={
                    historyLoading
                  }
                >
                  {historyLoading && history.length === 0
                    ? "Loading..."
                    : "↻ Refresh"}
                </button>

                <button
                  className="clear-button"
                  onClick={
                    clearHistory
                  }
                  disabled={
                    historyLoading ||
                    history.length === 0
                  }
                >
                  🗑 Clear
                </button>

              </div>
            </div>

            {/* TOTAL */}

            <div className="history-summary">

              Total Activities:{" "}

              <strong>
                {history.length}
              </strong>

            </div>

            {/* CONTENT */}

            {historyLoading &&
            history.length === 0 ? (

              <div className="empty">
                Loading activity history...
              </div>

            ) : history.length === 0 ? (

              <div className="empty">
                No activity history found.
                <br />
                Start the Activity Collector to record activities.
              </div>

            ) : (

              <div className="history-table-container">

                <table className="history-table">

                  <thead>

                    <tr>
                      <th>#</th>
                      <th>
                        Application
                      </th>
                      <th>
                        Window
                      </th>
                      <th>
                        Start Time
                      </th>
                      <th>
                        End Time
                      </th>
                      <th>
                        Duration
                      </th>
                      <th>
                        Classification
                      </th>
                    </tr>

                  </thead>

                  <tbody>

                    {history.map(
                      (
                        item,
                        index
                      ) => {

                        const application =
                          item.Application ||
                          item.application ||
                          "Unknown";

                        const window =
                          item.Window ||
                          item.window ||
                          "Unknown";

                        const startTime =
                          item[
                            "Start Time"
                          ] ||
                          item.start_time ||
                          "—";

                        const endTime =
                          item[
                            "End Time"
                          ] ||
                          item.end_time ||
                          "—";

                        const itemClassification =
                          getItemClassification(
                            item
                          );

                        let duration = 0;

                        if (
                          item[
                            "Duration (seconds)"
                          ] !==
                          undefined
                        ) {
                          duration =
                            Number(
                              item[
                                "Duration (seconds)"
                              ]
                            );
                        } else if (
                          item.duration !==
                          undefined
                        ) {
                          duration =
                            Number(
                              item.duration
                            );
                        }

                        return (
                          <tr
                            key={`${index}-${startTime}-${application}-${window}`}
                          >

                            <td>
                              {index + 1}
                            </td>

                            <td>
                              <b>
                                {
                                  application
                                }
                              </b>
                            </td>

                            <td className="window-cell">
                              {window}
                            </td>

                            <td>
                              {startTime}
                            </td>

                            <td>
                              {endTime}
                            </td>

                            <td>
                              {isNaN(
                                duration
                              )
                                ? "0.00"
                                : duration.toFixed(
                                    2
                                  )}{" "}
                              sec
                            </td>

                            <td>

                              <span
                                className={getClassificationClass(
                                  itemClassification
                                )}
                              >
                                {
                                  itemClassification
                                }
                              </span>

                            </td>

                          </tr>
                        );
                      }
                    )}

                  </tbody>

                </table>

              </div>
            )}

          </div>
        </section>
      );
    };

  // =====================================================
  // FOCUS FINGERPRINT PAGE
  // =====================================================

  const FocusFingerprintPage =
    () => {
      // Calculate the historical average directly from activity timestamps.
      // This prevents stale/corrupted profile recovery values from appearing.
      const fingerprintAverageRecovery =
        calculateAverageRecovery(history);

      return (
        <section className="fingerprint-page">

          {/* MAIN FINGERPRINT PANEL */}

          <div className="panel">

            <div className="panel-title">

              <div>
                <h2>
                  🧠 Focus Fingerprint
                </h2>

                <p>
                  Personal study behavior analysis
                </p>
              </div>

            </div>

            {!profile ? (

              <div className="empty">
                Loading Focus Fingerprint...
              </div>

            ) : (

              <div className="fingerprint-grid">

                <div>
                  <span>
                    Productive Activity
                  </span>

                  <strong>
                    {Math.round(
                      profile.productive_percentage ||
                        0
                    )}%
                  </strong>
                </div>

                <div>
                  <span>
                    Total Distractions
                  </span>

                  <strong>
                    {profile.total_distractions ||
                      0}
                  </strong>
                </div>

                <div>
                  <span>
                    Distractive Time
                  </span>

                  <strong>
                    {Math.round(
                      profile.distractive_time ||
                        0
                    )}{" "}
                    sec
                  </strong>
                </div>

                <div>
                  <span>
                    Average Recovery
                  </span>

                  <strong>
                    {Math.round(
                      fingerprintAverageRecovery ||
                        0
                    )}{" "}
                    sec
                  </strong>
                </div>

                <div>
                  <span>
                    Task Switches
                  </span>

                  <strong>
                    {profile.task_switches ||
                      0}
                  </strong>
                </div>

                <div>
                  <span>
                    Common Distraction
                  </span>

                  <strong>
                    {profile.common_distraction ||
                      "None"}
                  </strong>
                </div>

              </div>
            )}

          </div>

          {/* FOCUS SUMMARY */}

          {profile && (

            <div className="panel">

              <h2>
                📊 Focus Summary
              </h2>

              <div className="summary-box">

                <div className="summary-title">
                  Current Focus Performance
                </div>

                <div className="focus-score-large">
                  {Math.round(
                    profile.productive_percentage ||
                      0
                  )}%
                </div>

                <p className="summary-message">

                  {profile.productive_percentage >=
                  80
                    ? "Excellent focus performance. You are spending most of your study time on productive activities."
                    : profile.productive_percentage >=
                      60
                    ? "Good focus performance, but there is still some room to reduce distractions."
                    : "Your focus can be improved by reducing distracting activities and unnecessary task switching."}

                </p>

                <div className="summary-details">

                  <div>
                    <strong>
                      🎯 Main Distraction
                    </strong>

                    <span>
                      {profile.common_distraction &&
                      profile.common_distraction !==
                        "None"
                        ? profile.common_distraction
                        : "None detected"}
                    </span>
                  </div>

                  <div>
                    <strong>
                      🔄 Recovery
                    </strong>

                    <span>
                      {Math.round(
                        fingerprintAverageRecovery ||
                          0
                      )}{" "}
                      sec average recovery time
                    </span>
                  </div>

                  <div>
                    <strong>
                      🔀 Task Switching
                    </strong>

                    <span>
                      {profile.task_switches ||
                        0}{" "}
                      task switches detected
                    </span>
                  </div>

                </div>

                <div className="focus-recommendation">

                  <strong>
                    💡 Recommendation
                  </strong>

                  <p>
                    {profile.productive_percentage >=
                    80
                      ? "Continue your current study routine and try to maintain this level of focus."
                      : "Try keeping distracting websites closed during study sessions and return to your main task quickly after interruptions."}
                  </p>

                </div>

              </div>

            </div>
          )}

        </section>
      );
    };

  // =====================================================
  // REPORTS PAGE
  // =====================================================

  const ReportsPage =
    () => {

      // Reports must use saved activities from the latest completed session.
      // While a session is active, the live history remains useful.
      const reportActivities =
        sessionActive && history.length > 0
          ? history
          : reportHistory;

      let productiveCount = 0;
      let distractiveCount = 0;
      let neutralCount = 0;

      let productiveSeconds = 0;
      let distractiveSeconds = 0;
      let neutralSeconds = 0;

      reportActivities.forEach(
        (item) => {

          const itemClassification =
            getItemClassification(
              item
            );

          let duration = 0;

          if (
            item[
              "Duration (seconds)"
            ] !== undefined
          ) {
            duration =
              Number(
                item[
                  "Duration (seconds)"
                ]
              );
          } else if (
            item.duration !==
            undefined
          ) {
            duration =
              Number(
                item.duration
              );
          }

          if (isNaN(duration)) {
            duration = 0;
          }

          if (
            itemClassification ===
            "Productive"
          ) {
            productiveCount++;
            productiveSeconds +=
              duration;
          } else if (
            itemClassification ===
            "Distractive"
          ) {
            distractiveCount++;
            distractiveSeconds +=
              duration;
          } else {
            neutralCount++;
            neutralSeconds +=
              duration;
          }
        }
      );

      const totalTrackedSeconds =
        productiveSeconds +
        distractiveSeconds +
        neutralSeconds;

      const focusTrackedSeconds =
        productiveSeconds +
        distractiveSeconds;

      const reportProductivePercentage =
        focusTrackedSeconds > 0
          ? (productiveSeconds /
              focusTrackedSeconds) *
            100
          : Number(
              profile?.productive_percentage ||
                0
            );

      const productiveBar =
        totalTrackedSeconds > 0
          ? (productiveSeconds /
              totalTrackedSeconds) *
            100
          : 0;

      const distractiveBar =
        totalTrackedSeconds > 0
          ? (distractiveSeconds /
              totalTrackedSeconds) *
            100
          : 0;

      const neutralBar =
        totalTrackedSeconds > 0
          ? (neutralSeconds /
              totalTrackedSeconds) *
            100
          : 0;

      // Calculate Average Recovery from the actual activity timeline.
      // A newer Distractive activity replaces the previous recovery anchor,
      // and Neutral activities do not complete recovery.
      const averageRecovery =
        calculateAverageRecovery(reportActivities);

      const totalDistractions =
        profile?.total_distractions ??
        distractiveCount;

      const taskSwitches =
        profile?.task_switches || 0;

      // Use the same merged session list shown in Study Session History.
      // This keeps the Reports session count consistent with the actual
      // sessions visible to the user and avoids mismatches from backend
      // profile/cache data.
      const sessions =
        Array.isArray(studySessions)
          ? studySessions.length
          : 0;

      const commonDistraction =
        profile?.common_distraction ||
        "None";

      return (
        <section className="reports-page">

          {/* REPORT HEADER */}

          <div className="panel reports-header">

            <div className="panel-title">

              <div>
                <h2>
                  📈 FocusSense Reports
                </h2>

                <p>
                  Detailed analysis of your study behavior and productivity
                </p>
              </div>

              <button
                className="refresh-button"
                onClick={() => {
                  getData();
                  getReportsData();
                  getStudySessions();
                }}
                disabled={
                  historyLoading
                }
              >
                {historyLoading && history.length === 0
                  ? "Loading..."
                  : "↻ Refresh Report"}
              </button>

            </div>
          </div>

          {/* REPORT STATISTICS */}

          <div className="report-stat-grid">

            {/* PRODUCTIVE */}

            <div className="report-stat-card">

              <span className="report-stat-icon green">
                ✓
              </span>

              <div>
                <p>
                  Productive Time
                </p>

                <h2>
                  {Math.round(
                    profile?.productive_time ??
                      productiveSeconds
                  )}{" "}
                  sec
                </h2>
              </div>

            </div>

            {/* DISTRACTIVE */}

            <div className="report-stat-card">

              <span className="report-stat-icon red">
                !
              </span>

              <div>
                <p>
                  Distractive Time
                </p>

                <h2>
                  {Math.round(
                    profile?.distractive_time ??
                      distractiveSeconds
                  )}{" "}
                  sec
                </h2>
              </div>

            </div>

            {/* FOCUS SCORE */}

            <div className="report-stat-card">

              <span className="report-stat-icon purple">
                ★
              </span>

              <div>
                <p>
                  Focus Score
                </p>

                <h2>
                  {Math.round(
                    profile?.productive_percentage ??
                      reportProductivePercentage
                  )}

                  <span>
                    /100
                  </span>
                </h2>
              </div>

            </div>

            {/* RECOVERY */}

            <div className="report-stat-card">

              <span className="report-stat-icon blue">
                ↻
              </span>

              <div>
                <p>
                  Average Recovery
                </p>

                <h2>
                  {Math.round(
                    averageRecovery
                  )}{" "}
                  sec
                </h2>
              </div>

            </div>

          </div>

          {/* ACTIVITY DISTRIBUTION */}

          <div className="panel report-panel">

            <div className="panel-title">

              <div>
                <h2>
                  📊 Activity Distribution
                </h2>

                <p>
                  Breakdown of tracked activities
                </p>
              </div>

            </div>

            {reportLoading &&
            reportActivities.length === 0 ? (

              <div className="empty">
                Loading report data...
              </div>

            ) : reportActivities.length === 0 ? (

              <div className="empty">
                No activity data available for the report.
                <br />
                Start the Activity Collector to generate reports.
              </div>

            ) : (

              <div className="report-bars">

                {/* PRODUCTIVE */}

                <div className="report-bar-row">

                  <div className="report-bar-label">

                    <span>
                      ✓ Productive
                    </span>

                    <strong>
                      {productiveCount}{" "}
                      activities
                    </strong>

                  </div>

                  <div className="report-bar-background">

                    <div
                      className="report-bar productive-bar"
                      style={{
                        width: `${productiveBar}%`
                      }}
                    />

                  </div>

                  <div className="report-bar-value">
                    {Math.round(
                      productiveBar
                    )}%
                  </div>

                </div>

                {/* DISTRACTIVE */}

                <div className="report-bar-row">

                  <div className="report-bar-label">

                    <span>
                      ! Distractive
                    </span>

                    <strong>
                      {distractiveCount}{" "}
                      activities
                    </strong>

                  </div>

                  <div className="report-bar-background">

                    <div
                      className="report-bar distractive-bar"
                      style={{
                        width: `${distractiveBar}%`
                      }}
                    />

                  </div>

                  <div className="report-bar-value">
                    {Math.round(
                      distractiveBar
                    )}%
                  </div>

                </div>

                {/* NEUTRAL */}

                <div className="report-bar-row">

                  <div className="report-bar-label">

                    <span>
                      • Neutral
                    </span>

                    <strong>
                      {neutralCount}{" "}
                      activities
                    </strong>

                  </div>

                  <div className="report-bar-background">

                    <div
                      className="report-bar neutral-bar"
                      style={{
                        width: `${neutralBar}%`
                      }}
                    />

                  </div>

                  <div className="report-bar-value">
                    {Math.round(
                      neutralBar
                    )}%
                  </div>

                </div>

              </div>
            )}

          </div>

          {/* PERFORMANCE DETAILS */}

          <section className="reports-grid">

            {/* PRODUCTIVITY */}

            <div className="panel">

              <h2>
                🎯 Productivity Performance
              </h2>

              <div className="report-detail-list">

                <div>
                  <span>
                    Productivity Percentage
                  </span>

                  <strong>
                    {Math.round(
                      profile?.productive_percentage ??
                        reportProductivePercentage
                    )}%
                  </strong>
                </div>

                <div>
                  <span>
                    Total Productive Activities
                  </span>

                  <strong>
                    {productiveCount}
                  </strong>
                </div>

                <div>
                  <span>
                    Total Tracked Activities
                  </span>

                  <strong>
                    {reportActivities.length}
                  </strong>
                </div>

                <div>
                  <span>
                    Total Tracked Time
                  </span>

                  <strong>
                    {Math.round(
                      totalTrackedSeconds
                    )}{" "}
                    sec
                  </strong>
                </div>

              </div>

            </div>

            {/* DISTRACTION */}

            <div className="panel">

              <h2>
                ⚠ Distraction Analysis
              </h2>

              <div className="report-detail-list">

                <div>
                  <span>
                    Total Distractions
                  </span>

                  <strong>
                    {totalDistractions}
                  </strong>
                </div>

                <div>
                  <span>
                    Distractive Activities
                  </span>

                  <strong>
                    {distractiveCount}
                  </strong>
                </div>

                <div>
                  <span>
                    Common Distraction
                  </span>

                  <strong>
                    {commonDistraction}
                  </strong>
                </div>

                <div>
                  <span>
                    Distractive Time
                  </span>

                  <strong>
                    {Math.round(
                      profile?.distractive_time ??
                        distractiveSeconds
                    )}{" "}
                    sec
                  </strong>
                </div>

              </div>

            </div>

            {/* RECOVERY */}

            <div className="panel">

              <h2>
                🔄 Recovery Analysis
              </h2>

              <div className="report-detail-list">

                <div>
                  <span>
                    Average Recovery
                  </span>

                  <strong>
                    {Math.round(
                      averageRecovery
                    )}{" "}
                    sec
                  </strong>
                </div>

                <div>
                  <span>
                    Task Switches
                  </span>

                  <strong>
                    {taskSwitches}
                  </strong>
                </div>

                <div>
                  <span>
                    Sessions
                  </span>

                  <strong>
                    {sessions}
                  </strong>
                </div>

                <div>
                  <span>
                    Recovery Status
                  </span>

                  <strong>
                    {averageRecovery <=
                    20
                      ? "Fast"
                      : averageRecovery <=
                        40
                      ? "Moderate"
                      : "Slow"}
                  </strong>
                </div>

              </div>

            </div>

            {/* FOCUS RECOMMENDATION */}

            <div className="panel">

              <h2>
                💡 Focus Recommendation
              </h2>

              <div className="report-recommendation">

                <div className="recommendation-score">
                  {Math.round(
                    profile?.productive_percentage ??
                      reportProductivePercentage
                  )}%
                </div>

                <p>
                  {(profile?.productive_percentage ??
                    reportProductivePercentage) >=
                  80
                    ? "Excellent focus. Continue your current study routine and maintain your productive habits."
                    : (profile?.productive_percentage ??
                        reportProductivePercentage) >=
                      60
                    ? "Your focus is good, but reducing distractions can further improve your study performance."
                    : "Your focus needs improvement. Reduce distracting websites and avoid unnecessary task switching during study sessions."}
                </p>

              </div>

            </div>

          </section>

          {/* REPORT FOOTER */}

          <div className="panel report-footer">

            <strong>
              FocusSense Intelligence
            </strong>

            <p>
              This report is generated from the activity collected by the FocusSense Activity Collector.
              The results represent observed desktop activity during your study sessions.
            </p>

          </div>

        </section>
      );
    };

  // =====================================================
  // WAIT FOR AUTH CHECK
  // =====================================================

  if (!authReady) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "20px", fontWeight: "600" }}>
        Loading FocusSense...
      </div>
    );
  }

  // =====================================================
  // AUTH SCREEN
  // =====================================================

  if (!isLoggedIn) {
    return authPage === "register"
      ? renderRegisterPage()
      : renderLoginPage();
  }

  // =====================================================
  // MAIN RETURN
  // =====================================================

  return (
    <div className="dashboard">

      {/* SIDEBAR */}

      <aside className="sidebar">

        {/* LOGO */}

        <div className="logo">

          🧠

          <div>
            <h2>
              FocusSense
            </h2>

            <span>
              Study Intelligence
            </span>
          </div>

        </div>

        {/* NAVIGATION */}

        <nav>

          {/* DASHBOARD */}

          <div
            className={
              currentPage ===
              "dashboard"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() =>
              setCurrentPage(
                "dashboard"
              )
            }
          >
            📊 Dashboard
          </div>

          {/* STUDY SESSION */}

          <div
            className={
              currentPage ===
              "study-session"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() =>
              setCurrentPage(
                "study-session"
              )
            }
          >
            ▶️ Study Session
          </div>

          {/* STUDY SESSION HISTORY */}

          <div
            className={
              currentPage ===
              "study-history"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() =>
              setCurrentPage(
                "study-history"
              )
            }
          >
            📚 Study Session History
          </div>

          {/* HISTORY */}

          <div
            className={
              currentPage ===
              "history"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() =>
              setCurrentPage(
                "history"
              )
            }
          >
            🕒 Activity History
          </div>

          {/* FINGERPRINT */}

          <div
            className={
              currentPage ===
              "fingerprint"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() =>
              setCurrentPage(
                "fingerprint"
              )
            }
          >
            🧠 Focus Fingerprint
          </div>

          {/* REPORTS */}

          <div
            className={
              currentPage ===
              "reports"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() =>
              setCurrentPage(
                "reports"
              )
            }
          >
            📈 Reports
          </div>

        </nav>

        {/* COLLECTOR STATUS */}

        <div className="collector">

          <span
            className={
              connected
                ? "live-dot"
                : "offline-dot"
            }
          />

          <div>

            <strong>
              {connected
                ? "Collector Active"
                : "Backend Offline"}
            </strong>

            <small>
              {connected
                ? "Monitoring activity"
                : "Cannot connect to FastAPI"}
            </small>

          </div>

        </div>

      </aside>

      {/* MAIN */}

      <main className="main">

        {/* TOP BAR */}

        <header className="topbar">

          <div>

            <h1>

              {currentPage ===
              "history"
                ? "Activity History"

                : currentPage ===
                  "study-history"
                ? "Study Session History"

                : currentPage ===
                  "fingerprint"
                ? "Focus Fingerprint"
                : currentPage ===
                  "reports"
                ? "Reports"
                : currentPage ===
                  "study-session"
                ? "Study Session"
                : "FocusSense Dashboard"}

            </h1>

            <p>
              Context-Aware Digital Study Behavior Intelligence
            </p>

          </div>

          <div className="student">
            <span className="live-dot" />
            <b>LIVE</b>
            <div className="avatar">
              {username ? username.charAt(0).toUpperCase() : "P"}
            </div>
            <span>{username || "Student"}</span>
            <button
              onClick={handleLogout}
              style={{
                marginLeft: "12px",
                padding: "8px 12px",
                border: "none",
                borderRadius: "8px",
                background: "#ef4444",
                color: "#ffffff",
                cursor: "pointer",
                fontWeight: "600",
              }}
              title={userEmail ? `Logged in as ${userEmail}` : "Logout"}
            >
              Logout
            </button>
          </div>

        </header>

        {/* PAGE */}

        {currentPage ===
        "dashboard" ? (

          <DashboardPage />

        ) : currentPage ===
          "study-session" ? (

          renderStudySessionPage()

        ) : currentPage ===
          "study-history" ? (

          <StudySessionHistoryPage />

        ) : currentPage ===
          "history" ? (

          <ActivityHistoryPage />

        ) : currentPage ===
          "fingerprint" ? (

          <FocusFingerprintPage />

        ) : currentPage ===
          "reports" ? (

          <ReportsPage />

        ) : (

          <DashboardPage />

        )}

      </main>

    </div>
  );
}

export default App;
