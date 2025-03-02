// global.js

// Global AJAX error handler to catch 401 Unauthorized errors.
$(document).ajaxError(function(event, jqXHR, ajaxSettings, thrownError) {
  if (jqXHR.status === 401) {
    console.error("AJAX Error 401: Unauthorized. Details:", thrownError);
    // Clear authentication-related localStorage items.
    localStorage.removeItem("jwtToken");
    localStorage.removeItem("userRole");
    localStorage.removeItem("username");
    // Redirect the user to the login page.
    window.location.href = "/";
  }
});

document.addEventListener("DOMContentLoaded", function() {
  // Update the UI with the current user's name.
  const currentUserElem = document.getElementById("currentUser");
  const username = localStorage.getItem("username") || "Unknown";
  if (currentUserElem) {
    currentUserElem.textContent = username;
  }
  
  // Attach a click event to the logout button.
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", function() {
      console.log("Logout initiated. Clearing session data.");
      localStorage.removeItem("jwtToken");
      localStorage.removeItem("userRole");
      localStorage.removeItem("username");
      window.location.href = "/";
    });
  }
  
  // If no token is found, redirect to the login page.
  if (!localStorage.getItem("jwtToken")) {
    console.warn("No JWT token found. Redirecting to login.");
    window.location.href = "/";
  }

    // Hide admin link if the user's role is not admin.
  const userRole = localStorage.getItem("userRole") || "";
  if (userRole !== "admin") {
    const adminLink = document.getElementById("adminLink");
    if (adminLink) {
      adminLink.style.display = "none";
    }
  }
});
