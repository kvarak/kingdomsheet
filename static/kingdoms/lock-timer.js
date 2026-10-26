// Counts down the edit lock shown in the top right. Without JavaScript the minutes stay static.
(() => {
  const timer = document.getElementById("lock-timer");
  if (!timer) return;
  const end = Date.now() + Number(timer.dataset.seconds) * 1000;
  const tick = () => {
    const left = Math.max(0, Math.round((end - Date.now()) / 1000));
    timer.textContent = left
      ? `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`
      : "expired";
    timer.classList.toggle("lock-low", left > 0 && left <= 120);
    timer.classList.toggle("lock-expired", left === 0);
    if (left) setTimeout(tick, 1000);
  };
  tick();
})();
