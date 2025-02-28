// sensorChart.js

/**
 * Retrieves computed theme colors based on the current Bootstrap theme.
 * Returns an object containing colors for ticks, border, and background.
 */
function getComputedThemeColors() {
  const currentTheme = document.documentElement.getAttribute("data-bs-theme") || "light";
  if (currentTheme === "dark") {
    return {
      tickColor: "#e0e0e0",
      borderColor: "rgba(200,200,200,1)",
      backgroundColor: "rgba(200,200,200,0.2)"
    };
  } else {
    return {
      tickColor: "#000000",
      borderColor: "rgba(75,192,192,1)",
      backgroundColor: "rgba(75,192,192,0.2)"
    };
  }
}

/**
 * Debounce function: ensures that a function (fn) is not called more frequently than the specified delay.
 * @param {function} fn - Function to debounce.
 * @param {number} delay - Delay in milliseconds.
 * @returns {function}
 */
function debounce(fn, delay) {
  let timeoutId;
  return function(...args) {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * Initializes a live-updating line chart for the given sensor type.
 * @param {string} sensorType - The type of sensor (e.g., "temperature", "humidity").
 * @param {string} canvasId - The ID of the canvas element where the chart will be rendered.
 */
function initSensorChart(sensorType, canvasId) {
  const colors = getComputedThemeColors();
  const ctx = document.getElementById(canvasId).getContext('2d');
  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: sensorType.charAt(0).toUpperCase() + sensorType.slice(1) + ' Trend',
        data: [],
        borderColor: colors.borderColor,
        backgroundColor: colors.backgroundColor,
        fill: false,
        tension: 0.1
      }]
    },
    options: {
      responsive: true,
      scales: {
        x: {
          type: 'time',
          time: {
            tooltipFormat: 'HH:mm:ss',
            displayFormats: { minute: 'HH:mm' }
          },
          ticks: {
            color: colors.tickColor
          }
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: colors.tickColor
          }
        }
      },
      plugins: {
        legend: { display: true }
      }
    }
  });

  // Function to update the chart data by fetching sensor logs.
  async function updateChartData() {
    try {
      const response = await fetch(`/api/sensor/logs?type=${sensorType}`, {
        headers: { 'x-access-token': localStorage.getItem("jwtToken") || "" }
      });
      let data = await response.json();
      
      // Retrieve the time window once.
      const timeWindowSelector = document.getElementById("timeWindowSelector");
      const timeWindowHours = timeWindowSelector ? parseInt(timeWindowSelector.value) : 12;
      const cutoff = new Date(Date.now() - timeWindowHours * 60 * 60 * 1000);

      // Filter data to include only entries newer than the cutoff.
      data = data.filter(entry => new Date(entry.timestamp) >= cutoff);
      
      // Sort the logs by timestamp (ascending).
      data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
      
      chart.data.labels = data.map(entry => new Date(entry.timestamp));
      chart.data.datasets[0].data = data.map(entry => entry.value);
      chart.update();
    } catch (error) {
      console.error("Error fetching sensor logs for", sensorType, error);
    }
  }

  // Debounced update for the time window change.
  const debouncedUpdate = debounce(updateChartData, 300);

  // Initial update.
  updateChartData();
  // Poll for updates every minute.
  setInterval(updateChartData, 60000);
  
  // Attach event listener to update chart data when time window selection changes.
  const timeWindowSelector = document.getElementById("timeWindowSelector");
  if (timeWindowSelector) {
    timeWindowSelector.addEventListener("change", debouncedUpdate);
  }

  // Store chart globally for theme updates.
  window.charts = window.charts || [];
  window.charts.push(chart);

  return chart;
}
