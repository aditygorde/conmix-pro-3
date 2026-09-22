const form = document.getElementById("mixForm");
const results = document.getElementById("results");
const empty = document.getElementById("empty");
const errorBox = document.getElementById("error");

const setText = (id, value) => {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
};

const formatNumber = (value, digits = 2) => {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "—";
};

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorBox.classList.add("hidden");
  const data = Object.fromEntries(new FormData(form).entries());

  for (const k of ["aggregate_size", "slump", "sg_cement", "sg_fine", "sg_coarse", "admixture_dosage"]) {
    data[k] = Number(data[k]);
  }

  const button = form.querySelector(".calculate");
  button.disabled = true;
  button.querySelector("span").textContent = "Calculating…";

  try {
    const response = await fetch("/api/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(data)
    });

    const raw = await response.text();
    let payload;

    try {
      payload = raw ? JSON.parse(raw) : {};
    } catch (_) {
      throw new Error(
        `API returned a non-JSON response (${response.status}). ` +
        `${raw.substring(0, 240) || "No response body."}`
      );
    }

    if (!response.ok) {
      throw new Error(payload.detail || `Calculation failed (HTTP ${response.status}).`);
    }

    empty.classList.add("hidden");
    results.classList.remove("hidden");
    setText("resultGrade", payload.grade);
    setText("mixRatio", payload.mix_ratio);
    setText("target", formatNumber(payload.target_mean_strength_mpa));
    setText("wc", formatNumber(payload.governing_wc, 3));
    setText("cement", formatNumber(payload.cement_kg_m3));
    setText("water", formatNumber(payload.water_kg_m3));
    setText("fa", formatNumber(payload.fine_aggregate_kg_m3));
    setText("ca", formatNumber(payload.coarse_aggregate_kg_m3));
    setText("strengthWc", formatNumber(payload.strength_based_wc, 3));
    setText("maxWc", formatNumber(payload.maximum_wc_is456, 3));
    setText("air", formatNumber(payload.entrapped_air_percent) + "%");
    setText("caf", formatNumber(payload.ca_fraction, 3));

    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const note = warnings.length
      ? warnings.join(" ")
      : (payload.note || "First-trial mix. Verify with laboratory trial mixes.");
    setText("note", note);
  } catch (err) {
    results.classList.add("hidden");
    empty.classList.remove("hidden");
    errorBox.textContent = err?.message || "Unable to calculate the mix. Please try again.";
    errorBox.classList.remove("hidden");
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "Calculate mix design";
  }
});
