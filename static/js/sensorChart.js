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
 * Debounce function to limit how frequently a function is called.
 * @param {function} fn - The function to debounce.
 * @param {number} delay - Delay in milliseconds.
 * @returns {function}
 */
function debounce(fn, delay) {
  let timeoutId;
  return function(...args) {
    if (timeoutId) clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * Initializes a live-updating line chart for a sensor.
 * @param {string} sensorName - The unique sensor identifier (as stored in the database).
 * @param {string} canvasId - The ID of the canvas element where the chart will be rendered.
 */
function initSensorChart(sensorName, canvasId) {
  const canvasElement = document.getElementById(canvasId);
  if (!canvasElement) {
    console.error("Canvas element not found for ID:", canvasId);
    return;
  }
  
  const colors = getComputedThemeColors();
  const ctx = canvasElement.getContext('2d');
  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: sensorName + ' Trend',
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
          ticks: { color: colors.tickColor }
        },
        y: {
          beginAtZero: true,
          ticks: { color: colors.tickColor }
        }
      },
      plugins: { legend: { display: true } }
    }
  });

  // Function to update chart data by fetching sensor logs filtered by sensorName.
  async function updateChartData() {
    try {
      const response = await fetch(`/api/sensor/logs?type=${encodeURIComponent(sensorName)}`, {
        headers: { 'x-access-token': localStorage.getItem("jwtToken") || "" }
      });
      let data = await response.json();
      
      // Get the time window in hours from the drop-down, default to 12 hours.
      const timeWindowSelector = document.getElementById("timeWindowSelector");
      const timeWindowHours = timeWindowSelector ? parseInt(timeWindowSelector.value) : 12;
      const cutoff = new Date(Date.now() - timeWindowHours * 60 * 60 * 1000);
      
      // Filter data: only include entries newer than cutoff.
      data = data.filter(entry => new Date(entry.timestamp) >= cutoff);
      
      // Sort the logs by timestamp (ascending).
      data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
      
      chart.data.labels = data.map(entry => new Date(entry.timestamp));
      chart.data.datasets[0].data = data.map(entry => entry.value);
      chart.update();
    } catch (error) {
      console.error("Error fetching sensor logs for", sensorName, error);
    }
  }

  // Use a debounced version of the update function for time window changes.
  const debouncedUpdate = debounce(updateChartData, 300);
  
  // Initial update.
  updateChartData();
  // Poll for updates every minute.
  setInterval(updateChartData, 60000);
  // Update chart immediately when time window selection changes.
  if (timeWindowSelector) {
    timeWindowSelector.addEventListener("change", debouncedUpdate);
  }
  
  // Store chart instance globally for theme updates.
  window.charts = window.charts || [];
  window.charts.push(chart);
  
  return chart;
}
