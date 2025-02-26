document.addEventListener("DOMContentLoaded", function() {
  // Retrieve saved theme or default to "light"
  let currentTheme = localStorage.getItem("theme") || "light";
  document.documentElement.setAttribute("data-theme", currentTheme);

  // Update the theme icon based on current theme
  const themeToggle = document.getElementById("themeToggle");
  if (currentTheme === "dark") {
    themeToggle.src = "/static/img/moon.png";
  } else {
    themeToggle.src = "/static/img/sun.png";
  }

  // Toggle theme on icon click
  themeToggle.addEventListener("click", function() {
    // Toggle the theme
    currentTheme = (currentTheme === "light") ? "dark" : "light";
    // Save the new theme in localStorage
    localStorage.setItem("theme", currentTheme);
    // Update the data attribute on the html element
    document.documentElement.setAttribute("data-theme", currentTheme);
    // Update the icon accordingly
    themeToggle.src = (currentTheme === "dark") ? "/static/img/moon.png" : "/static/img/sun.png";

    // Update charts if necessary
    updateAllChartsTheme(currentTheme);
  });
});

// Optional: Function to update Chart.js charts when theme changes.
// Assume that you store your charts in a global array "window.charts".
function updateAllChartsTheme(theme) {
  if (window.charts && window.charts.length > 0) {
    window.charts.forEach(chart => {
      if (theme === "dark") {
        chart.options.scales.x.ticks.color = "#e0e0e0";
        chart.options.scales.y.ticks.color = "#e0e0e0";
        chart.data.datasets[0].borderColor = "rgba(200,200,200,1)";
        chart.data.datasets[0].backgroundColor = "rgba(200,200,200,0.2)";
      } else {
        chart.options.scales.x.ticks.color = "#000000";
        chart.options.scales.y.ticks.color = "#000000";
        chart.data.datasets[0].borderColor = "rgba(75,192,192,1)";
        chart.data.datasets[0].backgroundColor = "rgba(75,192,192,0.2)";
      }
      chart.update();
    });
  }
}
