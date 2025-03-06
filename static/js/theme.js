// theme.js

// Wait for the DOM content to be fully loaded before executing the code.
document.addEventListener("DOMContentLoaded", function() {
  // Retrieve the stored theme from localStorage; if none is found, default to "light".
  let currentTheme = localStorage.getItem("theme") || "light";
  
  // Get the theme toggle element from the DOM.
  // This is the clickable image that toggles between light and dark themes.
  const themeToggle = document.getElementById("themeToggle");
  if (!themeToggle) {
    console.error("Theme toggle element not found.");
    return; // Exit if the element is missing to avoid further errors.
  }
  
  // Apply the stored (or default) theme immediately on page load.
  setTheme(currentTheme);
  
  // Attach a click event listener to the theme toggle element.
  // When clicked, it toggles the current theme between "light" and "dark".
  themeToggle.addEventListener("click", function() {
    // Toggle the theme: if currently light, switch to dark; if dark, switch to light.
    currentTheme = (currentTheme === "light") ? "dark" : "light";
    // Save the updated theme in localStorage.
    localStorage.setItem("theme", currentTheme);
    // Apply the new theme.
    setTheme(currentTheme);
    // Update all existing charts to reflect the new theme colors.
    updateAllChartsTheme(currentTheme);
  });
  
  /**
   * setTheme(theme)
   * ---------------
   * Applies the specified theme to the document.
   * It updates the "data-bs-theme" attribute on the <html> element,
   * adjusts navbar classes, and changes the theme toggle icon.
   *
   * @param {string} theme - The theme to apply ("light" or "dark").
   */
  function setTheme(theme) {
    // Update the HTML element's data attribute to reflect the new theme.
    document.documentElement.setAttribute("data-bs-theme", theme);
    
    // Get the navbar element by its ID.
    const navBar = document.getElementById("mainNav");
    if (navBar) {
      if (theme === "dark") {
        // For dark theme: remove light-themed classes and add dark-themed classes.
        navBar.classList.remove("navbar-light", "bg-light");
        navBar.classList.add("navbar-dark", "bg-dark");
      } else {
        // For light theme: remove dark-themed classes and add light-themed classes.
        navBar.classList.remove("navbar-dark", "bg-dark");
        navBar.classList.add("navbar-light", "bg-light");
      }
    } else {
      console.warn("Navbar element not found.");
    }
    
    // Update the theme toggle icon based on the current theme.
    // If dark theme, display a moon icon; otherwise, display a sun icon.
    themeToggle.src = (theme === "dark") ? "/static/img/moon.svg" : "/static/img/sun.svg";
    console.log(`Theme set to ${theme}`);
  }
  
  /**
   * updateAllChartsTheme(theme)
   * ----------------------------
   * Updates the colors of all charts (stored in the global window.charts array)
   * to match the specified theme. This function assumes that each chart's options
   * follow the structure defined in sensorChart.js.
   *
   * @param {string} theme - The current theme ("light" or "dark").
   */
  function updateAllChartsTheme(theme) {
    // Check if there are any charts stored in the global window.charts array.
    if (window.charts && window.charts.length > 0) {
      // Define new color values based on the theme.
      const newColors = (theme === "dark")
        ? { tickColor: "#e0e0e0", borderColor: "rgba(200,200,200,1)", backgroundColor: "rgba(200,200,200,0.2)" }
        : { tickColor: "#000000", borderColor: "rgba(75,192,192,1)", backgroundColor: "rgba(75,192,192,0.2)" };
      
      // Iterate over each chart and update its options.
      window.charts.forEach(chart => {
        // Check if chart options for scales exist and update tick colors.
        if (chart.options && chart.options.scales) {
          if (chart.options.scales.x && chart.options.scales.x.ticks) {
            chart.options.scales.x.ticks.color = newColors.tickColor;
          }
          if (chart.options.scales.y && chart.options.scales.y.ticks) {
            chart.options.scales.y.ticks.color = newColors.tickColor;
          }
        }
        // Update the dataset colors (line and background).
        if (chart.data && chart.data.datasets && chart.data.datasets.length > 0) {
          chart.data.datasets[0].borderColor = newColors.borderColor;
          chart.data.datasets[0].backgroundColor = newColors.backgroundColor;
        }
        // Refresh the chart to apply the new colors.
        chart.update();
      });
      console.log("Updated all charts to theme", theme);
    } else {
      console.log("No charts found to update theme.");
    }
  }
});
