// global.js

/*
  Global AJAX error handler:
  This handler catches any AJAX error events globally.
  In particular, if an AJAX call returns a 401 Unauthorized error,
  it clears the stored authentication information and redirects the user to the login page.
*/
$(document).ajaxError(function(event, jqXHR, ajaxSettings, thrownError) {
  // Check if the HTTP status code is 401 (Unauthorized)
  if (jqXHR.status === 401) {
    console.error("AJAX Error 401: Unauthorized. Details:", thrownError);
    // Clear any stored JWT token and user information from localStorage
    localStorage.removeItem("jwtToken");
    localStorage.removeItem("userRole");
    localStorage.removeItem("username");
    // Redirect the user to the login page only if they are not already there
    if (window.location.pathname !== "/") {
      window.location.href = "/";
    }
  }
});

/*
  DOMContentLoaded event:
  This event fires when the initial HTML document has been completely loaded and parsed.
  The following code updates UI elements and attaches event handlers.
*/
document.addEventListener("DOMContentLoaded", function() {
  // -------------------------------
  // Update Current User Display
  // -------------------------------
  // Get the element where the current user's name should be displayed.
  const currentUserElem = document.getElementById("currentUser");
  // Retrieve the username from localStorage; default to "Unknown" if not found.
  const username = localStorage.getItem("username") || "Unknown";
  if (currentUserElem) {
    // Update the text content of the element with the username.
    currentUserElem.textContent = username;
  }
  
  // -------------------------------
  // Attach Logout Button Event Handler
  // -------------------------------
  // Get the logout button element.
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    // Attach a click event handler to the logout button.
    logoutBtn.addEventListener("click", function() {
      console.log("Logout initiated. Clearing session data.");
      // Clear authentication-related data from localStorage.
      localStorage.removeItem("jwtToken");
      localStorage.removeItem("userRole");
      localStorage.removeItem("username");
      // Redirect the user to the login page.
      window.location.href = "/";
    });
  }
  
  // -------------------------------
  // Check for JWT Token
  // -------------------------------
  // If no JWT token is found in localStorage and the user is not on the login page,
  // redirect them to the login page.
  if (!localStorage.getItem("jwtToken") && window.location.pathname !== "/" && window.location.pathname !== "/aboutpage" && window.location.pathname !== "/teampage" && window.location.pathname !== "/docpage") {
    console.warn("No JWT token found. Redirecting to login.");
    window.location.href = "/";
  }

  // -------------------------------
  // Hide Admin Link for Non-Admin Users
  // -------------------------------
  // Retrieve the user's role from localStorage.
  const userRole = localStorage.getItem("userRole") || "";
  // If the user is not an admin, hide the admin navigation link.
  if (userRole !== "admin") {
    const adminLink = document.getElementById("adminLink");
    if (adminLink) {
      adminLink.style.display = "none";
    }
  }
});
