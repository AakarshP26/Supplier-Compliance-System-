"""One-shot data migration: add city + state fields to seed_suppliers.json.

Strategy:
  1. Real listed Indian firms — assign their actual HQ city.
  2. Illustrative SMEs whose name carries a city (Mysuru, Pune, Noida, etc.)
     — keep that city.
  3. Illustrative SMEs without a city cue — default to Bangalore /
     Karnataka, since their profiles already use GSTIN state code 29.
  4. Foreign suppliers — leave city/state None.

After this migration ~70% of Indian suppliers will carry a Bangalore city
tag, matching the user's "India / Bangalore (mainly)" intent.
"""
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Real listed Indian firms with known HQ — explicit overrides
# ---------------------------------------------------------------------------

REAL_HQ = {
    "dixon-tech":               ("Noida",            "IN-UP"),
    "foxconn-india":            ("Sriperumbudur",    "IN-TN"),
    "pegatron-india":           ("Chennai",          "IN-TN"),
    "wistron-india":            ("Kolar",            "IN-KA"),  # Bangalore Rural
    "lava-international":       ("Noida",            "IN-UP"),
    "optiemus-electronics":     ("Noida",            "IN-UP"),
    "bhagwati-products":        ("Noida",            "IN-UP"),
    "amber-enterprises":        ("Gurugram",         "IN-HR"),
    "syrma-sgs":                ("Chennai",          "IN-TN"),
    "kaynes-tech":              ("Mysuru",           "IN-KA"),
    "tata-electronics":         ("Dholera",          "IN-GJ"),
    "vedanta-foxconn":          ("Sanand",           "IN-GJ"),
    "elcina-pcb-1":             ("Bengaluru",        "IN-KA"),
    "cyient-dlm":               ("Hyderabad",        "IN-TG"),
    "avalon-tech":              ("Chennai",          "IN-TN"),
    "epack-durables":           ("Greater Noida",    "IN-UP"),
    "vvdn-tech":                ("Manesar",          "IN-HR"),
    "sahasra-electronics":      ("Bhiwadi",          "IN-RJ"),
    "smile-electronics":        ("Bengaluru",        "IN-KA"),
    "centum-electronics":       ("Bengaluru",        "IN-KA"),
    "bharat-fih":               ("Sriperumbudur",    "IN-TN"),
    "moschip-tech":             ("Hyderabad",        "IN-TG"),
    "salcomp-india":            ("Chennai",          "IN-TN"),
    "jabil-india":              ("Pune",             "IN-MH"),
    "flex-india":               ("Chennai",          "IN-TN"),
    "bel-bengaluru":            ("Bengaluru",        "IN-KA"),
    "iti-limited":              ("Bengaluru",        "IN-KA"),
    "tejas-networks":           ("Bengaluru",        "IN-KA"),
    "hfcl":                     ("Gurugram",         "IN-HR"),
    "sterlite-tech":            ("Aurangabad",       "IN-MH"),
    "tata-elxsi":               ("Bengaluru",        "IN-KA"),
    "rakon-india":              ("Bengaluru",        "IN-KA"),
    "padmini-vna":              ("Manesar",          "IN-HR"),
    "bosch-india":              ("Bengaluru",        "IN-KA"),
    "honeywell-india":          ("Bengaluru",        "IN-KA"),
    "continental-india":        ("Bengaluru",        "IN-KA"),
    "saankhya-labs":            ("Bengaluru",        "IN-KA"),
    "signalchip":               ("Bengaluru",        "IN-KA"),
    "wipro-3d":                 ("Bengaluru",        "IN-KA"),
    "zetwerk":                  ("Bengaluru",        "IN-KA"),
    "tessolve":                 ("Bengaluru",        "IN-KA"),
    "tata-elxsi-whitefield":    ("Bengaluru",        "IN-KA"),
    "capgemini-engineering":    ("Bengaluru",        "IN-KA"),
}

# ---------------------------------------------------------------------------
# Cities decoded from supplier-name textual cues (illustrative SMEs etc.)
# ---------------------------------------------------------------------------

CITY_CUES = [
    ("mysuru-precision",         "Mysuru",         "IN-KA"),
    ("deccan-pcb",               "Hyderabad",      "IN-TG"),
    ("konkan-circuits",          "Pune",           "IN-MH"),
    ("punjab-power-mod",         "Mohali",         "IN-PB"),
    ("vellore-passives",         "Vellore",        "IN-TN"),
    ("kerala-coast-emd",         "Kochi",          "IN-KL"),
    ("ahmedabad-led",            "Ahmedabad",      "IN-GJ"),
    ("noida-pcb-tech",           "Noida",          "IN-UP"),
    ("chandigarh-instrument",    "Chandigarh",     "IN-CH"),
    ("tirupati-chip-test",       "Tirupati",       "IN-AP"),
    ("rajasthan-magnetics",      "Jaipur",         "IN-RJ"),
    ("bengal-broker-co",         "Kolkata",        "IN-WB"),
    ("indore-precision",         "Indore",         "IN-MP"),
    ("patna-control",            "Patna",          "IN-BR"),
    ("gurgaon-rf",               "Gurugram",       "IN-HR"),
]

# Foreign risky entities
FOREIGN = {
    "shenzhen-shadow-corp":     ("Shenzhen",       None),
    "guangdong-relabel":        ("Dongguan",       None),
    "dnipro-microelectronics":  ("Dnipro",         None),
    "shell-electronics-bvi":    ("Road Town",      None),
    "apex-global-sourcing":     ("Road Town",      None),
}

# ---------------------------------------------------------------------------
# Bangalore micro-locality assignment for unattributed illustrative SMEs.
# We round-robin through Karnataka industrial clusters so the dashboard
# shows a believable spread within Bangalore.
# ---------------------------------------------------------------------------

BANGALORE_LOCALITIES = [
    "Bengaluru — Peenya Industrial Area",
    "Bengaluru — Whitefield",
    "Bengaluru — Electronic City",
    "Bengaluru — Bommasandra Industrial Area",
    "Bengaluru — Jigani Industrial Area",
    "Bengaluru — Attibele",
    "Bengaluru — KR Puram",
    "Bengaluru — Yeshwanthpur Industrial Suburb",
    "Bengaluru — Hebbal",
    "Bengaluru — Doddaballapur",
    "Bengaluru — Bidadi",
    "Bengaluru — Hoskote",
    "Bengaluru — Yelahanka",
    "Bengaluru — Mahadevapura",
    "Bengaluru — Hosur Road",
]


def main() -> None:
    path = Path(__file__).resolve().parent.parent / "data" / "seed_suppliers.json"
    suppliers = json.loads(path.read_text())

    locality_idx = 0
    for s in suppliers:
        sid = s["id"]

        # Already explicit?
        if sid in REAL_HQ:
            city, state = REAL_HQ[sid]
        elif sid in FOREIGN:
            city, state = FOREIGN[sid]
        else:
            cue = next((c for c in CITY_CUES if c[0] == sid), None)
            if cue:
                _, city, state = cue
            elif s["country"] == "IN":
                # Default unattributed Indian SMEs to a Bangalore locality
                city = BANGALORE_LOCALITIES[locality_idx % len(BANGALORE_LOCALITIES)]
                state = "IN-KA"
                locality_idx += 1
            else:
                city = None
                state = None

        s["city"] = city
        s["state"] = state

    path.write_text(json.dumps(suppliers, indent=2, ensure_ascii=False) + "\n")

    # Audit
    states = {}
    for s in suppliers:
        if s["country"] == "IN":
            states[s["state"]] = states.get(s["state"], 0) + 1
    print(f"Updated {len(suppliers)} suppliers with city/state.")
    print("Indian state distribution:")
    for st, n in sorted(states.items(), key=lambda x: -x[1]):
        print(f"  {st or '—':10s}  {n:3d}")
    bangalore = sum(1 for s in suppliers
                    if s.get("city") and s["city"].startswith("Beng"))
    print(f"Bangalore-area: {bangalore}")


if __name__ == "__main__":
    main()
