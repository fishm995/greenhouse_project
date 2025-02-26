document.addEventListener("DOMContentLoaded", function() {
  let currentTheme = localStorage.getItem("theme") || "light";
  
  // Move the themeToggle declaration to the top.
  const themeToggle = document.getElementById("themeToggle");

  // Now call setTheme after themeToggle is initialized.
  setTheme(currentTheme);

  themeToggle.addEventListener("click", function() {
    currentTheme = (currentTheme === "light") ? "dark" : "light";
    localStorage.setItem("theme", currentTheme);
    setTheme(currentTheme);
    updateAllChartsTheme(currentTheme);
  });

  function setTheme(theme) {
    document.documentElement.setAttribute("data-bs-theme", theme);
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

  function updateAllChartsTheme(theme) {
    // Code to update charts based on the new theme.
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
