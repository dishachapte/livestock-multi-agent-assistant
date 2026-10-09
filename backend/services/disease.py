"""Symptom-based screening for eight cattle conditions, plus milk-drop analysis.

This is a rule-based screening aid. It lists POSSIBLE conditions and the signs behind
each one. It never states a confirmed diagnosis, never shows a confidence number,
and never recommends medicines.
"""
from datetime import date, timedelta

DISCLAIMER = (
    "AI-assisted symptom screening, not a confirmed diagnosis. The conditions listed are "
    "possibilities only. A veterinarian must examine the animal to confirm."
)
FEVER_C = 39.5
HIGH_FEVER_C = 40.0
CRITICAL_TEMP_C = 41.0
MILK_DROP_ANOMALY_PCT = 25.0
NOTIFIABLE = {"Foot-and-Mouth Disease (FMD)", "Lumpy Skin Disease (LSD)"}
PRIORITY_FOR_ACTIONS = {"urgent": "high", "high": "high", "medium": "medium", "low": "low"}

DISEASE_GUIDE = {
    "Mastitis": "Ask the veterinarian for a milk test before any treatment. Keep milking equipment clean.",
    "Foot-and-Mouth Disease (FMD)": "Isolate the animal now and report it to your local animal health authority as required. Call a veterinarian immediately.",
    "Lumpy Skin Disease (LSD)": "Isolate the animal and report it to the animal health authority. Ask the veterinarian about insect control.",
    "Bovine Respiratory Disease": "Keep the animal in a dry, draft-free shelter. A veterinarian should examine it.",
    "Milk Fever": "This needs urgent veterinary treatment. Do not wait.",
    "Bloat": "A bloated animal can get worse quickly. Call a veterinarian now.",
    "Ketosis": "A veterinarian should check ketone levels. Make sure the animal has access to feed and water.",
    "Foot Rot": "Keep the foot clean and dry. A veterinarian or hoof trimmer should examine it.",
}
NEXT_STEP_BY_PRIORITY = {
    "urgent": "Call a veterinarian now. Isolate the animal from the herd while you wait.",
    "high": "Arrange a veterinary examination today.",
    "medium": "Check temperature, appetite and milk again within a few hours. Call a veterinarian if signs get worse.",
    "low": "Continue routine monitoring.",
}


def _signs(*pairs) -> list[str]:
    """Keep only the labels whose condition is true."""
    return [label for condition, label in pairs if condition]


def assess(report: dict, animal_id: int, tag: str, name: str, today: date) -> dict:
    temp = report.get("temperature_c")
    before = report.get("milk_before_l")
    now_milk = report.get("milk_now_l")
    days = report.get("days_since_calving")
    appetite = report.get("appetite", "normal")
    udder = report.get("udder", "normal")
    abnormal_milk = report.get("milk_appearance", "normal") == "abnormal"

    fever = temp is not None and temp >= FEVER_C
    high_fever = temp is not None and temp >= HIGH_FEVER_C
    very_high_temp = temp is not None and temp >= CRITICAL_TEMP_C

    drop_pct = None
    if before and before > 0 and now_milk is not None:
        drop_pct = round((before - now_milk) / before * 100, 1)
    milk_anomaly = drop_pct is not None and drop_pct >= MILK_DROP_ANOMALY_PCT

    udder_abnormal = udder != "normal"
    appetite_down = appetite != "normal"
    recently_calved = days is not None and days <= 3
    ketosis_window = days is not None and 5 <= days <= 60
    limping = bool(report.get("limping"))
    feet = bool(report.get("foot_lesions"))
    mouth = bool(report.get("mouth_blisters"))
    nodules = bool(report.get("skin_nodules"))
    cough = bool(report.get("cough_or_nasal_discharge"))
    breath = bool(report.get("breathing_difficulty"))
    bloat = bool(report.get("bloated_left_side"))
    down = bool(report.get("unable_to_stand"))
    tremble = bool(report.get("trembling"))

    # ---- Possible conditions, each with the signs that support it ----
    conditions: list[dict] = []

    def add(condition: str, signs: list[str]) -> None:
        if signs:
            conditions.append({"name": condition, "matched_signs": signs})

    if udder_abnormal and (abnormal_milk or milk_anomaly or fever):
        add("Mastitis", _signs(
            (True, f"udder {udder.replace('_', ' ')}"),
            (abnormal_milk, "abnormal milk"),
            (milk_anomaly, f"milk down {drop_pct}%"),
            (fever, f"temperature {temp} C"),
        ))
    if mouth or (fever and feet):
        add("Foot-and-Mouth Disease (FMD)", _signs(
            (mouth, "blisters in mouth"),
            (feet, "foot lesions"),
            (fever, f"temperature {temp} C"),
        ))
    if nodules:
        add("Lumpy Skin Disease (LSD)", _signs(
            (True, "skin nodules"),
            (fever, f"temperature {temp} C"),
        ))
    if cough and (fever or breath):
        add("Bovine Respiratory Disease", _signs(
            (cough, "cough or nasal discharge"),
            (fever, f"temperature {temp} C"),
            (breath, "difficulty breathing"),
        ))
    if recently_calved and (down or tremble):
        add("Milk Fever", _signs(
            (True, f"calved {days} day(s) ago"),
            (down, "unable to stand"),
            (tremble, "trembling"),
            (appetite_down, f"appetite {appetite}"),
        ))
    if bloat:
        add("Bloat", _signs(
            (True, "swollen left side"),
            (breath, "difficulty breathing"),
        ))
    if ketosis_window and appetite_down and milk_anomaly and not fever:
        add("Ketosis", _signs(
            (True, f"calved {days} days ago"),
            (appetite_down, f"appetite {appetite}"),
            (milk_anomaly, f"milk down {drop_pct}%"),
        ))
    if limping and feet and not mouth:
        add("Foot Rot", _signs(
            (limping, "limping"),
            (feet, "foot lesions"),
        ))

    # ---- Severity ----
    urgent_reasons = _signs(
        (breath, "difficulty breathing"),
        (down, "unable to stand"),
        (bloat, "swollen left side (bloat can worsen quickly)"),
        (very_high_temp, f"temperature {temp} C is very high"),
    )
    condition_names = {c["name"] for c in conditions}
    if condition_names & NOTIFIABLE:
        urgent_reasons.append("possible notifiable disease (FMD or LSD)")

    any_flag = any([limping, feet, mouth, nodules, cough, breath, bloat, down, tremble])
    symptoms_present = fever or udder_abnormal or abnormal_milk or appetite_down or milk_anomaly or any_flag

    if urgent_reasons:
        priority = "urgent"
    elif high_fever or milk_anomaly or conditions:
        priority = "high"
    elif symptoms_present:
        priority = "medium"
    else:
        priority = "low"

    # ---- Concerns shared with the Farm Manager ----
    concerns = _signs(
        (fever, f"Temperature {temp} C (fever)"),
        (drop_pct is not None and drop_pct > 0,
         f"Milk fell from {before} L to {now_milk} L per day ({drop_pct}% drop)"),
        (udder_abnormal, f"Udder is {udder.replace('_', ' ')}"),
        (abnormal_milk, "Milk looks abnormal"),
        (appetite_down, f"Appetite is {appetite}"),
        (limping, "Limping"),
        (feet, "Foot lesions"),
        (mouth, "Blisters in mouth"),
        (nodules, "Skin nodules"),
        (cough, "Cough or nasal discharge"),
        (breath, "Difficulty breathing"),
        (bloat, "Swollen left side"),
        (down, "Unable to stand"),
        (tremble, "Trembling"),
    )

    next_steps = [NEXT_STEP_BY_PRIORITY[priority]] + [DISEASE_GUIDE[c["name"]] for c in conditions]

    # ---- Proposed actions (the farmer still approves each one) ----
    label = f"{name} ({tag})"
    target = f"animal:{tag}"
    reason = "Symptom report: " + "; ".join(concerns + [c["name"] for c in conditions]) if (concerns or conditions) else "Symptom report"
    base_params = {"target": target, "label": label, "animal_id": animal_id}
    actions: list[dict] = []

    if priority in ("urgent", "high"):
        requested = today if priority == "urgent" else today + timedelta(days=1)
        actions.append({
            "action_type": "book_vet",
            "priority": PRIORITY_FOR_ACTIONS[priority],
            "reason": reason,
            "parameters": {**base_params, "requested_for": requested.isoformat()},
        })
        actions.append({
            "action_type": "flag_animal",
            "priority": "high",
            "reason": reason,
            "parameters": dict(base_params),
        })
    elif milk_anomaly:
        actions.append({
            "action_type": "flag_animal",
            "priority": "medium",
            "reason": reason,
            "parameters": dict(base_params),
        })

    return {
        "animal_id": animal_id,
        "animal_tag": tag,
        "animal_label": label,
        "priority": priority,
        "urgent_reasons": urgent_reasons,
        "possible_conditions": conditions,
        "concerns": concerns,
        "recommended_next_steps": next_steps,
        "milk_drop_percent": drop_pct,
        "milk_production_anomaly": milk_anomaly,
        "actions": actions,
        "assessed_on": today.isoformat(),
        "disclaimer": DISCLAIMER,
    }
