// sensorChart.js

/**
 * getComputedThemeColors()
 * --------------------------
 * This function returns a set of colors based on the current Bootstrap theme.
 * It reads the "data-bs-theme" attribute from the <html> element and returns
 * different colors for dark and light themes. These colors are used to style the charts.
 *
 * Returns:
 *   An object with the following properties:
 *     - tickColor: The color used for axis ticks.
 *     - borderColor: The color used for the chart line (border).
 *     - backgroundColor: The color used for the area below the chart line (if filled).
 */
function getComputedThemeColors() {
  // Get the current theme (e.g., "light" or "dark"). Default to "light" if not set.
  const currentTheme = document.documentElement.getAttribute("data-bs-theme") || "light";
  if (currentTheme === "dark") {
    // Return colors for the dark theme.
    return {
      tickColor: "#e0e0e0",
      borderColor: "rgba(200,200,200,1)",
      backgroundColor: "rgba(200,200,200,0.2)"
    };
  } else {
    // Return colors for the light theme.
    return {
      tickColor: "#000000",
      borderColor: "rgba(75,192,192,1)",
      backgroundColor: "rgba(75,192,192,0.2)"
    };
  }
}

/**
 * debounce(fn, delay)
 * --------------------
 * A debounce function limits how often a given function can be executed.
 * It returns a new function that, when invoked, delays the execution of the original
 * function until after the specified delay has passed since its last invocation.
 *
 * Parameters:
 *   - fn: The function to debounce.
 *   - delay: The delay time in milliseconds.
 *
 * Returns:
 *   A debounced version of the input function.
 */
function debounce(fn, delay) {
  let timeoutId;
  return function(...args) {
    // If there's a pending timeout, clear it.
    if (timeoutId) clearTimeout(timeoutId);
    // Set a new timeout to execute the function after the delay.
    timeoutId = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * initSensorChart(sensorName, canvasId)
 * -------------------------------------
 * Initializes a live-updating line chart for a sensor using Chart.js.
 *
 * Parameters:
 *   - sensorName (string): The unique identifier of the sensor (as stored in the database).
 *   - canvasId (string): The ID of the <canvas> element where the chart will be rendered.
 *
 * Returns:
 *   The Chart.js chart instance.
 *
 * This function performs the following steps:
 *   1. Retrieves the canvas element by ID and verifies it exists.
 *   2. Gets the current theme colors using getComputedThemeColors().
 *   3. Creates a Chart.js line chart with initial empty data.
 *   4. Defines an async function updateChartData() that fetches sensor logs,
 *      filters them based on a selected time window, sorts them by timestamp,
 *      and updates the chart data accordingly.
 *   5. Calls updateChartData() immediately and then sets an interval to call it every minute.
 *   6. Attaches a debounced event listener to a time window selector to update the chart when the selection changes.
 *   7. Stores the chart instance globally (for theme updates) and returns it.
 */
function initSensorChart(sensorName, canvasId) {
  // Retrieve the canvas element where the chart will be rendered.
  const canvasElement = document.getElementById(canvasId);
  if (!canvasElement) {
    console.error("Canvas element not found for ID:", canvasId);
    return;
  }
  
  // Get theme-based colors for the chart.
  const colors = getComputedThemeColors();
  // Get the drawing context of the canvas.
  const ctx = canvasElement.getContext('2d');
  // Create a new line chart using Chart.js.
  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      // Initially, there are no labels (x-axis) and no data points.
      labels: [],
      datasets: [{
        label: sensorName + ' Trend', // Chart label includes the sensor name.
        data: [],
        borderColor: colors.borderColor,       // Use the computed border color.
        backgroundColor: colors.backgroundColor, // Use the computed background color.
        fill: false,       // Do not fill under the line.
        tension: 0.1       // Set curve tension for smoothing the line.
      }]
    },
    options: {
      responsive: true,  // Make the chart responsive to screen size.
      scales: {
        x: {
          type: 'time',  // The x-axis represents time.
          time: {
            tooltipFormat: 'HH:mm:ss',  // Format for tooltips on the time axis.
            displayFormats: { minute: 'HH:mm' }  // How time is displayed on the x-axis.
          },
          ticks: { color: colors.tickColor }  // Set tick color based on theme.
        },
        y: {
          beginAtZero: true,  // y-axis starts at zero.
          ticks: { color: colors.tickColor }  // Set tick color based on theme.
        }
      },
      plugins: { legend: { display: true } }  // Display the chart legend.
    }
  });

  /**
   * updateChartData()
   * -----------------
   * Asynchronously fetches sensor logs from the /api/sensor/logs endpoint,
   * filters them based on the selected time window, sorts them in ascending order,
   * and updates the chart's data.
   */
  async function updateChartData() {
    try {
      // Fetch sensor logs for the given sensorName. The API expects a "type" query parameter.
      const response = await fetch(`/api/sensor/logs?type=${encodeURIComponent(sensorName)}`, {
        headers: { 'x-access-token': localStorage.getItem("jwtToken") || "" }
      });
      let data = await response.json();
      
      // Retrieve the time window (in hours) from a drop-down element (if present).
      const timeWindowSelector = document.getElementById("timeWindowSelector");
      // Default to 12 hours if the selector is not present.
      const timeWindowHours = timeWindowSelector ? parseInt(timeWindowSelector.value) : 12;
      // Calculate the cutoff time: only logs after this time will be shown.
      const cutoff = new Date(Date.now() - timeWindowHours * 60 * 60 * 1000);
      
      // Filter the data: include only log entries whose timestamp is after the cutoff time.
      data = data.filter(entry => new Date(entry.timestamp) >= cutoff);
      
      // Sort the filtered log entries in ascending order based on timestamp.
      data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
      
      // Update chart labels (x-axis) with the timestamps.
      chart.data.labels = data.map(entry => new Date(entry.timestamp));
      // Update the dataset with the sensor values.
      chart.data.datasets[0].data = data.map(entry => entry.value);
      // Refresh the chart to display the updated data.
      chart.update();
    } catch (error) {
      console.error("Error fetching sensor logs for", sensorName, error);
    }
  }

  // Create a debounced version of the updateChartData function to limit rapid updates.
  const debouncedUpdate = debounce(updateChartData, 300);
  
  // Call updateChartData immediately to load initial data.
  updateChartData();
  // Set up a timer to update the chart data every 60 seconds.
  setInterval(updateChartData, 60000);
  // If a time window selector exists, update the chart immediately when its value changes.
  if (timeWindowSelector) {
    timeWindowSelector.addEventListener("change", debouncedUpdate);
  }
  
  // Store the chart instance globally so it can be updated later (e.g., when the theme changes).
  window.charts = window.charts || [];
  window.charts.push(chart);
  
  // Return the created chart instance.
  return chart;
}
