"""
ConMix Pro — Concrete Mix Design API

Calculation framework:
- IS 10262:2019 — Concrete Mix Proportioning — Guidelines
- IS 456:2000 — Plain and Reinforced Concrete — Code of Practice

Important engineering note:
The strength-vs-w/c curves in this demo are illustrative defaults. IS 10262
requires the strength relationship to be established from actual materials and
trial mixes. This application therefore reports warnings instead of blocking
calculation when a selected grade/exposure combination needs engineering review.
"""

from typing import List
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Concrete Mix Design by Python", version="2.0.0")
BASE_DIR = Path(__file__).resolve().parent.parent

GRADES = {
    "M15": 15, "M20": 20, "M25": 25, "M30": 30,
    "M35": 35, "M40": 40, "M45": 45, "M50": 50,
}

# Durability inputs used for the normal RCC design mode in this calculator.
EXPOSURE = {
    "Mild": {"min_cement": 300, "max_wc": 0.55, "min_grade": 20},
    "Moderate": {"min_cement": 300, "max_wc": 0.50, "min_grade": 25},
    "Severe": {"min_cement": 320, "max_wc": 0.45, "min_grade": 30},
    "Very Severe": {"min_cement": 340, "max_wc": 0.45, "min_grade": 35},
    "Extreme": {"min_cement": 360, "max_wc": 0.40, "min_grade": 40},
}

STD_DEV = [(15, 3.5), (25, 4.0), (50, 5.0)]
WATER = {10: 208, 20: 186, 40: 165}
AIR = {10: 1.5, 20: 1.0, 40: 0.8}

CA_FRACTION = {
    10: {"Zone I": 0.44, "Zone II": 0.46, "Zone III": 0.48, "Zone IV": 0.50},
    20: {"Zone I": 0.60, "Zone II": 0.62, "Zone III": 0.64, "Zone IV": 0.66},
    40: {"Zone I": 0.69, "Zone II": 0.71, "Zone III": 0.73, "Zone IV": 0.75},
}

# Illustrative defaults only. Replace with laboratory strength/w-c data for
# project use. Values are keyed as water/cement ratio -> compressive strength.
CURVES = {
    "OPC43": {0.35: 43, 0.40: 37, 0.45: 32, 0.50: 27, 0.55: 22, 0.60: 17},
    "OPC53": {0.35: 48, 0.40: 43, 0.45: 38, 0.50: 33, 0.55: 28, 0.60: 23},
}

# Guard rails used only to keep the demo calculator numerically stable for all
# supported grades. Values outside the laboratory curve are flagged as warnings.
MIN_WC_CURVE = 0.30
MAX_WC_CURVE = 0.65


class MixInput(BaseModel):
    grade: str = "M25"
    exposure: str = "Moderate"
    aggregate_size: int = Field(20, description="10, 20 or 40 mm")
    sand_zone: str = "Zone II"
    cement_type: str = "OPC43"
    slump: float = Field(50, gt=0, le=180)
    sg_cement: float = Field(3.15, gt=2.0, le=4.0)
    sg_fine: float = Field(2.65, gt=2.0, le=3.5)
    sg_coarse: float = Field(2.70, gt=2.0, le=3.5)
    admixture_dosage: float = Field(0.0, ge=0, le=50)
    sg_admixture: float = Field(1.145, gt=0.5, le=2.0)


def std_dev(fck: float) -> float:
    for upper, s in STD_DEV:
        if fck <= upper:
            return s
    return 5.0


def interpolate_wc_with_warning(target: float, curve: dict) -> tuple[float, List[str]]:
    """Return a usable illustrative w/c value without throwing for high grades."""
    pts = sorted(curve.items())
    strengths = [s for _, s in pts]
    warnings: List[str] = []

    if target > max(strengths):
        # Extrapolate from the two strongest points, then clamp to a practical
        # demo guard rail. The result is explicitly marked as provisional.
        (wc1, s1), (wc2, s2) = pts[0], pts[1]
        extrapolated = wc1 + (target - s1) * (wc2 - wc1) / (s2 - s1)
        wc = max(MIN_WC_CURVE, min(MAX_WC_CURVE, extrapolated))
        warnings.append(
            f"Target mean strength {target:.2f} MPa is above the illustrative "
            f"{curve and max(strengths):.0f} MPa curve range. A provisional "
            f"w/c of {wc:.3f} was used; replace it with project trial-mix data."
        )
        return wc, warnings

    if target < min(strengths):
        (wc1, s1), (wc2, s2) = pts[-2], pts[-1]
        extrapolated = wc1 + (target - s1) * (wc2 - wc1) / (s2 - s1)
        wc = max(MIN_WC_CURVE, min(MAX_WC_CURVE, extrapolated))
        warnings.append(
            f"Target mean strength {target:.2f} MPa is below the illustrative "
            f"curve range. A provisional w/c of {wc:.3f} was used."
        )
        return wc, warnings

    for (wc1, s1), (wc2, s2) in zip(pts, pts[1:]):
        if s1 >= target >= s2:
            return wc1 + (target - s1) * (wc2 - wc1) / (s2 - s1), warnings

    # Defensive fallback; should not be reached for valid sorted curves.
    return 0.50, ["The strength curve could not be interpolated; provisional w/c 0.500 was used."]


def calculate(inp: MixInput):
    if inp.grade not in GRADES:
        raise ValueError("Grade must be M15, M20, M25, M30, M35, M40, M45 or M50.")
    if inp.exposure not in EXPOSURE:
        raise ValueError("Invalid exposure condition.")
    if inp.aggregate_size not in WATER:
        raise ValueError("Aggregate size must be 10, 20 or 40 mm.")
    if inp.sand_zone not in CA_FRACTION[inp.aggregate_size]:
        raise ValueError("Sand zone must be Zone I, Zone II, Zone III or Zone IV.")
    if inp.cement_type not in CURVES:
        raise ValueError("Cement type must be OPC43 or OPC53.")

    fck = GRADES[inp.grade]
    exp = EXPOSURE[inp.exposure]
    warnings: List[str] = []

    if fck < exp["min_grade"]:
        warnings.append(
            f"{inp.grade} is below the normal RCC minimum grade M{exp['min_grade']} "
            f"listed for {inp.exposure} exposure. Verify the applicable structural "
            "and durability requirements before use."
        )

    s = std_dev(fck)
    target = fck + 1.65 * s

    strength_wc, curve_warnings = interpolate_wc_with_warning(target, CURVES[inp.cement_type])
    warnings.extend(curve_warnings)

    governing_wc = min(strength_wc, exp["max_wc"])
    if exp["max_wc"] < strength_wc:
        warnings.append(
            f"Durability maximum w/c of {exp['max_wc']:.2f} governs over the "
            f"illustrative strength-based value of {strength_wc:.3f}."
        )

    water = float(WATER[inp.aggregate_size])
    if inp.slump > 50:
        water *= 1 + 0.03 * ((inp.slump - 50) / 25)

    # The displayed dosage is treated as an absolute admixture mass. A real
    # project mix should use the manufacturer's tested water-reduction factor.
    cement = max(water / governing_wc, exp["min_cement"])
    if cement > 450:
        warnings.append(
            f"Calculated cement content is {cement:.1f} kg/m³, above the 450 kg/m³ "
            "reference limit used by this calculator. Review materials, admixture "
            "water reduction and trial mixes; the value is not presented as an approval."
        )

    ca_frac = CA_FRACTION[inp.aggregate_size][inp.sand_zone]
    ca_frac += ((0.50 - governing_wc) / 0.05) * 0.01
    ca_frac = max(0.0, min(1.0, ca_frac))

    air = AIR[inp.aggregate_size] / 100
    vc = cement / (inp.sg_cement * 1000)
    vw = water / 1000
    vad = inp.admixture_dosage / (inp.sg_admixture * 1000) if inp.admixture_dosage else 0
    vag = 1 - vc - vw - vad - air

    if vag <= 0:
        # This is an extreme/non-physical input combination. Keep the UI usable
        # and return a clearly flagged provisional aggregate quantity.
        warnings.append(
            "Calculated constituent volumes leave no positive aggregate volume. "
            "Aggregate quantities below are provisional zeros and must not be used "
            "without redesigning the water/cement/admixture inputs."
        )
        vca = vfa = 0.0
    else:
        vca = vag * ca_frac
        vfa = vag * (1 - ca_frac)

    ca = vca * inp.sg_coarse * 1000
    fa = vfa * inp.sg_fine * 1000

    return {
        "grade": inp.grade,
        "exposure": inp.exposure,
        "fck_mpa": round(fck, 3),
        "standard_deviation_mpa": round(s, 3),
        "target_mean_strength_mpa": round(target, 3),
        "strength_based_wc": round(strength_wc, 4),
        "maximum_wc_is456": round(exp["max_wc"], 4),
        "governing_wc": round(governing_wc, 4),
        "water_kg_m3": round(water, 2),
        "cement_kg_m3": round(cement, 2),
        "fine_aggregate_kg_m3": round(fa, 2),
        "coarse_aggregate_kg_m3": round(ca, 2),
        "ca_fraction": round(ca_frac, 4),
        "mix_ratio": f"1 : {fa/cement:.2f} : {ca/cement:.2f}" if cement else "N/A",
        "entrapped_air_percent": round(air * 100, 3),
        "admixture_kg_m3": round(inp.admixture_dosage, 2),
        "warnings": warnings,
        "warning": " ".join(warnings),
        "note": "First-trial mix. Verify and adjust using laboratory trial mixes with actual materials.",
        "method": "IS 10262:2019 mix proportioning framework + IS 456:2000 durability checks. Strength/w/c relationship is an illustrative default, not an IS table.",
    }


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(BASE_DIR / "index.html", media_type="text/html")


@app.get("/style.css", include_in_schema=False)
def stylesheet():
    return FileResponse(BASE_DIR / "style.css", media_type="text/css")


@app.get("/script.js", include_in_schema=False)
def javascript():
    return FileResponse(BASE_DIR / "script.js", media_type="application/javascript")


@app.get("/api")
def home():
    return {"name": "Concrete Mix Design by Python", "status": "ok", "version": "2.0.0"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/calculate")
def api_calculate(inp: MixInput):
    try:
        return calculate(inp)
    except ValueError as exc:
        # Always return JSON for expected input errors.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Prevent HTML/plain-text surprises from reaching the frontend.
        raise HTTPException(status_code=500, detail=f"Calculation engine error: {exc}") from exc
