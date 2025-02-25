    $(document).ajaxError(function(event, jqXHR, ajaxSettings, thrownError) {
      if (jqXHR.status === 401) {
      // Token expired or unauthorized: clear local storage and redirect to login.
      localStorage.removeItem("jwtToken");
      localStorage.removeItem("userRole");
      localStorage.removeItem("username");
      window.location.href = "/";  // redirect to index.html is your login page
      }
    });

    document.addEventListener("DOMContentLoaded", function() {
      const logoutBtn = document.getElementById("logoutBtn");
      if (logoutBtn) {
        logoutBtn.addEventListener("click", function(){
          localStorage.removeItem("jwtToken");
          localStorage.removeItem("userRole");
          localStorage.removeItem("username");
          window.location.href = "/"; // Redirect to login page
        });
      }
    });
