// "Copy unit summary": copies the text of the read-only box the button points at. Without
// clipboard access the box can still be selected and copied by hand.
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-target]");
  if (!button) return;
  const box = document.getElementById(button.dataset.copyTarget);
  try {
    await navigator.clipboard.writeText(box.value);
    button.textContent = "Copied";
  } catch {
    box.select();
    button.textContent = "Select and copy the text";
  }
});
