    $(document).ajaxError(function(event, jqXHR, ajaxSettings, thrownError) {
      if (jqXHR.status === 401) {
      // Token expired or unauthorized: clear local storage and redirect to login.
      localStorage.removeItem("jwtToken");
      localStorage.removeItem("userRole");
      localStorage.removeItem("username");
      window.location.href = "/";  // redirect to index.html is your login page
      }
    });
