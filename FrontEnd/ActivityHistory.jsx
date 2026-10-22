import { useEffect, useState } from "react";
import "./ActivityHistory.css";

function ActivityHistory() {

  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const API = "http://127.0.0.1:8000";


  // =====================================================
  // LOAD HISTORY
  // =====================================================

  const loadHistory = async () => {

    try {

      setLoading(true);
      setError("");

      const response = await fetch(
        `${API}/activity-history`
      );

      if (!response.ok) {

        throw new Error(
          "Unable to load activity history"
        );

      }

      const data = await response.json();

      setActivities(
        data.activities || []
      );

    } catch (err) {

      console.error(err);

      setError(
        "Cannot connect to FastAPI"
      );

    } finally {

      setLoading(false);

    }

  };


  // =====================================================
  // LOAD WHEN PAGE OPENS
  // =====================================================

  useEffect(() => {

    loadHistory();

  }, []);


  // =====================================================
  // CLEAR HISTORY
  // =====================================================

  const clearHistory = async () => {

    const confirmClear = window.confirm(
      "Are you sure you want to clear activity history?"
    );

    if (!confirmClear) {
      return;
    }


    try {

      const response = await fetch(
        `${API}/activity-history`,
        {
          method: "DELETE"
        }
      );


      const data = await response.json();


      if (data.status === "success") {

        setActivities([]);

      }

    } catch (err) {

      alert(
        "Cannot connect to FastAPI"
      );

    }

  };


  return (

    <div className="history-page">

      {/* HEADER */}

      <div className="history-header">

        <div>

          <h1>Activity History</h1>

          <p>
            View your recorded digital study activities
          </p>

        </div>


        <div className="history-buttons">

          <button
            className="refresh-btn"
            onClick={loadHistory}
          >
            ↻ Refresh
          </button>


          <button
            className="clear-btn"
            onClick={clearHistory}
          >
            🗑 Clear History
          </button>

        </div>

      </div>


      {/* ERROR */}

      {error && (

        <div className="error-box">

          ⚠ {error}

        </div>

      )}


      {/* LOADING */}

      {loading ? (

        <div className="loading">

          Loading activity history...

        </div>

      ) : activities.length === 0 ? (

        <div className="empty-history">

          <div className="empty-icon">
            📊
          </div>

          <h2>No Activity Found</h2>

          <p>
            Start the Activity Collector to record
            your computer activity.
          </p>

        </div>

      ) : (

        <div className="history-card">

          <div className="history-summary">

            <strong>
              {activities.length}
            </strong>

            <span>
              Activities Recorded
            </span>

          </div>


          <div className="table-container">

            <table>

              <thead>

                <tr>

                  <th>#</th>

                  <th>Application</th>

                  <th>Window</th>

                  <th>Start Time</th>

                  <th>End Time</th>

                  <th>Duration</th>

                </tr>

              </thead>


              <tbody>

                {activities.map(
                  (activity, index) => (

                  <tr key={index}>

                    <td>
                      {index + 1}
                    </td>

                    <td>

                      <strong>
                        {activity.Application}
                      </strong>

                    </td>

                    <td>

                      <span className="window-text">

                        {activity.Window}

                      </span>

                    </td>

                    <td>
                      {activity["Start Time"]}
                    </td>

                    <td>
                      {activity["End Time"]}
                    </td>

                    <td>

                      <span className="duration">

                        {activity[
                          "Duration (seconds)"
                        ]}

                        s

                      </span>

                    </td>

                  </tr>

                ))}

              </tbody>

            </table>

          </div>

        </div>

      )}

    </div>

  );

}

export default ActivityHistory;