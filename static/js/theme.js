document.addEventListener("DOMContentLoaded", function() {
  // Retrieve the stored theme or default to "light"
  let currentTheme = localStorage.getItem("theme") || "light";
  
  // Get theme toggle element (ensure it exists before using it)
  const themeToggle = document.getElementById("themeToggle");
  if (!themeToggle) {
    console.error("Theme toggle element not found.");
    return;
  }
  
  // Apply the stored theme
  setTheme(currentTheme);
  
  // Attach click listener to toggle theme
  themeToggle.addEventListener("click", function() {
    currentTheme = (currentTheme === "light") ? "dark" : "light";
    localStorage.setItem("theme", currentTheme);
    setTheme(currentTheme);
    updateAllChartsTheme(currentTheme);
  });
  
  /**
   * Sets the theme by updating the data-bs-theme attribute and toggling navbar classes and icon.
   * @param {string} theme - The current theme ("light" or "dark").
   */
  function setTheme(theme) {
    // Set Bootstrap theme attribute on the <html> element.
    document.documentElement.setAttribute("data-bs-theme", theme);
    
    // Update navbar classes if navbar element exists.
    const navBar = document.getElementById("mainNav");
    if (navBar) {
      if (theme === "dark") {
        navBar.classList.remove("navbar-light", "bg-light");
        navBar.classList.add("navbar-dark", "bg-dark");
      } else {
        navBar.classList.remove("navbar-dark", "bg-dark");
        navBar.classList.add("navbar-light", "bg-light");
      }
    } else {
      console.warn("Navbar element not found.");
    }
    
    // Update the theme toggle icon.
    themeToggle.src = (theme === "dark") ? "/static/img/moon.svg" : "/static/img/sun.svg";
    console.log(`Theme set to ${theme}`);
  }
  
  /**
   * Updates all charts in the global window.charts array with new colors based on the theme.
   * This function assumes that each chart's options follow the structure defined in sensorChart.js.
   * @param {string} theme - The current theme ("light" or "dark").
   */
  function updateAllChartsTheme(theme) {
    if (window.charts && window.charts.length > 0) {
      const newColors = (theme === "dark")
        ? { tickColor: "#e0e0e0", borderColor: "rgba(200,200,200,1)", backgroundColor: "rgba(200,200,200,0.2)" }
        : { tickColor: "#000000", borderColor: "rgba(75,192,192,1)", backgroundColor: "rgba(75,192,192,0.2)" };
      
      window.charts.forEach(chart => {
        if (chart.options && chart.options.scales) {
          if (chart.options.scales.x && chart.options.scales.x.ticks) {
            chart.options.scales.x.ticks.color = newColors.tickColor;
          }
          if (chart.options.scales.y && chart.options.scales.y.ticks) {
            chart.options.scales.y.ticks.color = newColors.tickColor;
          }
        }
        if (chart.data && chart.data.datasets && chart.data.datasets.length > 0) {
          chart.data.datasets[0].borderColor = newColors.borderColor;
          chart.data.datasets[0].backgroundColor = newColors.backgroundColor;
        }
        chart.update();
      });
      console.log("Updated all charts to theme", theme);
    } else {
      console.log("No charts found to update theme.");
    }
  }
});
