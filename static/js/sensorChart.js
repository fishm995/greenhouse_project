// sensorChart.js

/**
 * Initializes a live-updating line chart for the given sensor type.
 * @param {string} sensorType - The type of sensor (e.g., "temperature", "humidity").
 * @param {string} canvasId - The ID of the canvas element where the chart will be rendered.
 */

function getComputedThemeColors() {
  // Get the computed CSS variables from the document root.
  const rootStyles = getComputedStyle(document.documentElement);
  return {
    borderColor: rootStyles.getPropertyValue('--chart-border-color').trim(),
    backgroundColor: rootStyles.getPropertyValue('--chart-bg-color').trim(),
    tickColor: rootStyles.getPropertyValue('--chart-tick-color').trim()
  };
}

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

      // Get the selected time window (in hours) from the drop-down.
      const timeWindowSelector = document.getElementById("timeWindowSelector");
      const timeWindowHours = timeWindowSelector ? parseInt(timeWindowSelector.value) : 12;
      const cutoff = new Date(Date.now() - timeWindowHours * 60 * 60 * 1000);

      // Filter data to only include entries newer than cutoff.
      data = data.filter(entry => new Date(entry.timestamp) >= cutoff);
      
      // Assume data is an array of { timestamp, value }
      // Sort the logs by timestamp in ascending order.
      data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
      chart.data.labels = data.map(entry => new Date(entry.timestamp));
      chart.data.datasets[0].data = data.map(entry => entry.value);
      chart.update();
    } catch (error) {
      console.error("Error fetching sensor logs for", sensorType, error);
    }
  }

  // Initial update.
  updateChartData();
  // Poll for updates every minute (60000ms); adjust as needed.
  setInterval(updateChartData, 60000);
  
  // Update chart data immediately when the time window selection changes.
  const timeWindowSelector = document.getElementById("timeWindowSelector");
  if (timeWindowSelector) {
    timeWindowSelector.addEventListener("change", updateChartData);
  }

  window.charts = window.charts || [];
  window.charts.push(chart);

  return chart;
}
