document.addEventListener("DOMContentLoaded", function() {
  // Retrieve saved theme from localStorage (default is "light")
  let currentTheme = localStorage.getItem("theme") || "light";
  setTheme(currentTheme);

  const themeToggle = document.getElementById("themeToggle");
  themeToggle.addEventListener("click", function() {
    currentTheme = (currentTheme === "light") ? "dark" : "light";
    localStorage.setItem("theme", currentTheme);
    setTheme(currentTheme);
    // Optionally update charts if needed.
    updateAllChartsTheme(currentTheme);
  });

  function setTheme(theme) {
    // Set the Bootstrap theme attribute on the html element.
    document.documentElement.setAttribute("data-bs-theme", theme);
    // Update the nav bar by toggling classes (Bootstrap 5.3 uses data-bs-theme to automatically update most components,
    // but you might want to manually adjust some elements).
    const navBar = document.getElementById("mainNav");
    if (theme === "dark") {
      navBar.classList.remove("navbar-light", "bg-light");
      navBar.classList.add("navbar-dark", "bg-dark");
      themeToggle.src = "/static/img/moon.svg";
    } else {
      navBar.classList.remove("navbar-dark", "bg-dark");
      navBar.classList.add("navbar-light", "bg-light");
      themeToggle.src = "/static/img/sun.svg";
    }
  }

  // Optional: Function to update Chart.js charts when theme changes.
  function updateAllChartsTheme(theme) {
    if (window.charts && window.charts.length > 0) {
      const newColors = (theme === "dark") 
            ? { tickColor: "#e0e0e0", borderColor: "rgba(200,200,200,1)", backgroundColor: "rgba(200,200,200,0.2)" }
            : { tickColor: "#000000", borderColor: "rgba(75,192,192,1)", backgroundColor: "rgba(75,192,192,0.2)" };
      window.charts.forEach(chart => {
        chart.options.scales.x.ticks.color = newColors.tickColor;
        chart.options.scales.y.ticks.color = newColors.tickColor;
        chart.data.datasets[0].borderColor = newColors.borderColor;
        chart.data.datasets[0].backgroundColor = newColors.backgroundColor;
        chart.update();
      });
    }
  }
});
