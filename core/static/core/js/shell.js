(function () {
  var sidebar = document.getElementById("ft-sidebar");
  var toggle = document.getElementById("ft-sidebar-toggle");

  if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("ft-collapsed");
    });
  }
})();
