(function () {
  var choice = "auto";
  try {
    choice = localStorage.getItem("organiser-theme") || "auto";
  } catch (e) {}
  var theme = choice;
  if (theme !== "morning" && theme !== "evening") {
    var hour = 0;
    try {
      hour = Number(
        new Intl.DateTimeFormat("en-GB", {
          timeZone: "Europe/London",
          hour: "numeric",
          hourCycle: "h23",
        }).format(new Date()),
      );
    } catch (e) {}
    if (!isFinite(hour)) hour = 0;
    hour = ((hour % 24) + 24) % 24;
    theme = hour >= 5 && hour < 17 ? "morning" : "evening";
  }
  document.documentElement.setAttribute("data-theme", theme);
  var meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "morning" ? "#1b1916" : "#050403");
})();
