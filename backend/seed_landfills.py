"""South Florida disposal facilities: the one source of truth.

Every permitted place a hauler can tip a load in Palm Beach, Broward and
Miami-Dade, with FY26 gate rates. server.py seeds this into
landfill_facilities / tip_fees on boot (idempotent, keyed on name), the
dump-suggest endpoint ranks it, and the Dump Book page is generated from it.

Rates: SWA Rev 6 (eff 2025-11-01), Broward County (eff 2026-01-01), Broward
SWA gate-rate survey (Mar 2025) for private yards, Miami-Dade DSWM (eff
2025-10-01). "No fee rows" means the yard quotes at the gate.

Coordinates are geocoded from the street address to ~street-block accuracy;
fee_accuracy_validated stays False until a real weigh ticket confirms a row.
"""
from __future__ import annotations

from datetime import datetime, timezone

# access values: walk_in (any hauler at the scale) | account (WM/contract
# customers only) | permit (county hauler permit) | residents (not for us)
WALK_IN, ACCOUNT, PERMIT, RESIDENTS = "walk_in", "account", "permit", "residents"

_WEEK = {str(d): {"open": "07:00", "close": "17:00"} for d in range(6)}


def _hours(mf=("07:00", "17:00"), sat=None, sun=None):
    out = {str(d): {"open": mf[0], "close": mf[1]} for d in range(5)}
    if sat:
        out["5"] = {"open": sat[0], "close": sat[1]}
    if sun:
        out["6"] = {"open": sun[0], "close": sun[1]}
    return out


# --- rate sheets --------------------------------------------------------
SWA_TS_FEES = {"msw": 42, "bulky": 42, "mattress": 42, "metal": 42, "appliance_w_freon": 10,
               "yard": 35, "c_and_d": 80, "drywall": 80, "mixed": 80}
SWA_LF_FEES = dict(SWA_TS_FEES, concrete=80, tires=125)
BROWARD_LF_FEES = {"bulky": 100, "mattress": 100, "metal": 100, "appliance_w_freon": 100, "mixed": 100,
                   "c_and_d": 100, "drywall": 100, "concrete": 100, "yard": 75, "tires": 130}
WM_OAKES_FEES = {"bulky": 75, "mattress": 75, "metal": 75, "appliance_w_freon": 75, "mixed": 75,
                 "c_and_d": 68, "drywall": 68, "concrete": 68, "yard": 65}
MONARCH_FEES = {k: 105.51 for k in ("msw", "bulky", "mattress", "metal", "appliance_w_freon", "mixed",
                                     "c_and_d", "drywall", "concrete", "yard")}
REUTER_FEES = {k: 85 for k in ("msw", "bulky", "mattress", "metal", "mixed", "c_and_d", "drywall", "yard")}
MDC_LF_FEES = {k: 115.80 for k in ("msw", "bulky", "mattress", "metal", "appliance_w_freon", "mixed",
                                    "c_and_d", "drywall", "concrete", "yard")}
MDC_LF_FEES["tires"] = 140.0
MDC_TS_FEES = {k: 133.10 for k in ("msw", "bulky", "mattress", "metal", "mixed")}
MEDLEY_FEES = {k: 113.19 for k in ("msw", "bulky", "c_and_d", "yard", "mixed")}

SWA_TS_ACCEPTS = ["msw", "bulky", "mattress", "metal", "appliance_w_freon", "yard", "c_and_d", "drywall", "mixed"]
CD_YARD = ["c_and_d", "drywall", "concrete", "yard"]

SWA_TS_NOTE = ("Cash or Visa/MC/Discover at the scale. $10 minimum. Rejects concrete, block, brick, tile, "
               "rebar, roofing, lumber/trusses, pallets, dirt, sod, big stumps, tire loads — take those to the "
               "North County Landfill. Mixed loads billed at the highest category.")


def _f(name, type_, operator, address, lat, lon, county, accepts, hours, phone, access,
       fees=None, notes=None, origin_county=None, turnaround=25):
    return {
        "name": name, "type": type_, "operator": operator, "address": address,
        "lat": lat, "lon": lon, "county": county, "accepts_categories": accepts,
        "hours_json": hours, "phone": phone, "access": access, "fees": fees or {},
        "notes": notes, "origin_county": origin_county, "avg_turnaround_min": turnaround,
    }


FACILITIES = [
    # ------------------------------------------------------------ Palm Beach (SWA)
    _f("SWA North County Landfill", "landfill", "Solid Waste Authority of PBC",
       "6330 N Jog Rd, West Palm Beach, FL 33412", 26.7565, -80.1465, "palm-beach",
       SWA_TS_ACCEPTS + ["concrete", "tires"], _hours(("07:00", "17:00"), ("07:00", "17:00")),
       "+15616404000", WALK_IN, SWA_LF_FEES,
       "The only SWA site that takes concrete, roofing, lumber, tires and special waste. Cash or card. $10 minimum.",
       turnaround=30),
    _f("SWA Central County Transfer Station (Lantana)", "transfer_station", "Solid Waste Authority of PBC",
       "1810 Lantana Rd, Lantana, FL 33462", 26.5870, -80.0760, "palm-beach", SWA_TS_ACCEPTS,
       _hours(("07:00", "17:00"), ("07:00", "12:00")), "+15616972700", WALK_IN, SWA_TS_FEES, SWA_TS_NOTE),
    _f("SWA South County Transfer Station (Delray)", "transfer_station", "Solid Waste Authority of PBC",
       "1901 SW 4th Ave, Delray Beach, FL 33444", 26.4440, -80.0790, "palm-beach", SWA_TS_ACCEPTS,
       _hours(("07:00", "17:00"), ("07:00", "15:00")), "+15616972700", WALK_IN, SWA_TS_FEES, SWA_TS_NOTE),
    _f("SWA Southwest County Transfer Station (West Delray)", "transfer_station", "Solid Waste Authority of PBC",
       "13400 S State Rd 7, Delray Beach, FL 33446", 26.4300, -80.2000, "palm-beach", SWA_TS_ACCEPTS,
       _hours(("07:00", "17:00"), ("07:00", "15:00")), "+15616972700", WALK_IN, SWA_TS_FEES, SWA_TS_NOTE),
    _f("SWA West Central Transfer Station (Royal Palm Beach)", "transfer_station", "Solid Waste Authority of PBC",
       "9743 Weisman Way, Royal Palm Beach, FL 33411", 26.6975, -80.2240, "palm-beach", SWA_TS_ACCEPTS,
       _hours(("07:00", "17:00"), ("07:00", "15:00")), "+15616972700", WALK_IN, SWA_TS_FEES, SWA_TS_NOTE),
    _f("SWA North County Transfer Station (Jupiter)", "transfer_station", "Solid Waste Authority of PBC",
       "14185 N Military Trail, Jupiter, FL 33458", 26.9050, -80.1120, "palm-beach", SWA_TS_ACCEPTS,
       _hours(("07:00", "17:00"), ("07:00", "15:00")), "+15616972700", WALK_IN, SWA_TS_FEES, SWA_TS_NOTE),
    _f("SWA West County Transfer Station (Belle Glade)", "transfer_station", "Solid Waste Authority of PBC",
       "1701 State Rd 15, Belle Glade, FL 33430", 26.7050, -80.6720, "palm-beach", SWA_TS_ACCEPTS,
       _hours(("07:30", "16:00")), "+15616972700", WALK_IN, SWA_TS_FEES, SWA_TS_NOTE),
    _f("WM Recycling Lantana", "c_and_d", "WM", "790 Hillbrath Dr, Lantana, FL 33462", 26.5900, -80.0870,
       "palm-beach", CD_YARD, _hours(), "+15615826688", WALK_IN, None,
       "SWA-permitted C&D/yard recycler. No furniture or household bulk. Quotes at the gate."),
    _f("WM Recycling Palm Beach", "c_and_d", "WM", "6911 Wallis Rd, West Palm Beach, FL 33413", 26.7040, -80.1470,
       "palm-beach", CD_YARD, _hours(), "+15615826688", WALK_IN, None,
       "SWA-permitted C&D/yard recycler. No furniture or household bulk. Quotes at the gate."),
    _f("WM Recycling Riviera Beach", "c_and_d", "WM", "7095 Barbour Rd, Riviera Beach, FL 33412", 26.7690, -80.1390,
       "palm-beach", ["c_and_d", "drywall", "concrete"], _hours(), "+15615826688", WALK_IN, None,
       "SWA-permitted C&D recycler. Quotes at the gate."),
    _f("Coastal Waste & Recycling of Palm Beach", "c_and_d", "Coastal Waste & Recycling",
       "6759 Wallis Rd, West Palm Beach, FL 33413", 26.7040, -80.1450, "palm-beach", CD_YARD, _hours(),
       "+19549856750", WALK_IN, None, "SWA-permitted C&D/yard recycler. Quotes at the gate."),
    _f("Amerigrow Recycling (Delray)", "c_and_d", "Amerigrow", "10320 W Atlantic Ave, Delray Beach, FL 33446",
       26.4560, -80.1680, "palm-beach", ["yard"], _hours(), "+15614998148", WALK_IN, None, "Yard trash only."),
    _f("Atlas Peat & Soil (Boynton)", "c_and_d", "Atlas Peat & Soil", "9621 State Rd 7, Boynton Beach, FL 33437",
       26.5180, -80.2020, "palm-beach", ["yard"], _hours(), "+15617347300", WALK_IN, None, "Yard trash only."),
    _f("Debris Dog (Jupiter)", "c_and_d", "Debris Dog", "18505 Bee Line Hwy, Jupiter, FL 33478",
       26.8600, -80.2400, "palm-beach", ["yard"], _hours(), "+15616620498", WALK_IN, None, "Yard trash only."),
    _f("DS Eakins Construction (WPB)", "c_and_d", "DS Eakins", "550 Benoist Farms Rd, West Palm Beach, FL 33411",
       26.7100, -80.1830, "palm-beach", ["concrete"], _hours(), "+15618420001", WALK_IN, None,
       "Clean concrete and asphalt only."),

    # ------------------------------------------------------------ Broward
    _f("WM Recycling Oakes Road (Davie)", "c_and_d", "WM", "3250 SW 50th Ave, Davie, FL 33314", 26.0680, -80.2130,
       "broward", ["bulky", "mattress", "metal", "appliance_w_freon", "mixed", "c_and_d", "drywall", "concrete", "yard"],
       _hours(("06:00", "18:00"), ("06:00", "16:00")), "+15612022384", WALK_IN, WM_OAKES_FEES,
       "Takes residential walk-ins. Cheapest bulk and C&D in Broward. Gate rates per Broward SWA survey, Mar 2025."),
    _f("Broward County Landfill (Southwest Ranches)", "landfill", "Broward County",
       "7101 SW 205th Ave, Southwest Ranches, FL 33332", 26.0330, -80.4270, "broward",
       list(BROWARD_LF_FEES), _hours(("08:00", "16:00"), ("08:00", "16:00")), "+19547654999", WALK_IN,
       BROWARD_LF_FEES, "Class III: no household garbage. Broward-origin loads only. $10 minimum; $50 scale bypass.",
       origin_county="broward", turnaround=30),
    _f("WM Recycling Pompano", "c_and_d", "WM", "2281 NW 16th St, Pompano Beach, FL 33069", 26.2500, -80.1500,
       "broward", ["bulky", "mixed", "c_and_d", "drywall", "concrete", "yard"], _hours(("06:00", "18:00"), ("06:00", "13:00")),
       "+18009634776", WALK_IN, None, "Commercial and residential. Quotes at the gate."),
    _f("WM Recycling Dania Beach", "c_and_d", "WM", "3251 SW 26th Ter, Fort Lauderdale, FL 33312", 26.0900, -80.1720,
       "broward", ["bulky", "mixed", "c_and_d", "drywall", "concrete", "yard"], _hours(("05:00", "17:00"), ("05:00", "13:00")),
       "+15615378656", WALK_IN, None, "Quotes at the gate."),
    _f("WM Recycling Deerfield East", "c_and_d", "WM", "1801 SW 42nd Way, Deerfield Beach, FL 33442", 26.3010, -80.1400,
       "broward", ["c_and_d", "drywall", "yard", "appliance_w_freon", "metal"], _hours(("06:00", "18:00"), ("06:00", "13:00")),
       "+15612022372", WALK_IN, None, "Quotes at the gate."),
    _f("WM Recycling Deerfield West", "transfer_station", "WM", "1750 SW 43rd Ter, Deerfield Beach, FL 33442",
       26.3010, -80.1420, "broward", ["msw", "bulky", "c_and_d"], _hours(("06:00", "18:00")), "+18009634776", ACCOUNT, None,
       "Class I transfer. Contract customers only."),
    _f("Waste Connections Deerfield Beach", "transfer_station", "Waste Connections",
       "1751 SW 43rd Ter, Deerfield Beach, FL 33442", 26.3015, -80.1425, "broward",
       ["msw", "bulky", "mattress", "metal", "mixed", "c_and_d", "drywall", "concrete", "yard"],
       _hours(("06:00", "17:00"), ("06:00", "16:00")), "+19544266127", WALK_IN, None, "Quotes at the gate."),
    _f("Coastal Waste & Recycling #4 (Pompano)", "c_and_d", "Coastal Waste & Recycling",
       "1840 NW 33rd St, Pompano Beach, FL 33064", 26.2620, -80.1450, "broward",
       ["bulky", "mixed", "c_and_d", "drywall", "concrete", "yard"], _hours(("06:00", "18:00"), ("07:00", "14:00")),
       "+19549474000", WALK_IN, None, "Quotes at the gate."),
    _f("Coastal Nineteen MRF (Davie)", "mrf", "Coastal Waste & Recycling", "7061 SW 22nd Ct, Davie, FL 33317",
       26.0960, -80.2450, "broward", ["bulky", "c_and_d", "drywall", "concrete", "yard"], _hours(),
       "+19549474000", WALK_IN, None, "Quotes at the gate."),
    _f("All County Waste Recycling (Deerfield)", "c_and_d", "All County Waste Recycling",
       "1810 SW 42nd Way, Deerfield Beach, FL 33442", 26.3010, -80.1400, "broward",
       ["c_and_d", "drywall", "yard", "appliance_w_freon", "metal"], _hours(), None, WALK_IN, None, "Quotes at the gate."),
    _f("Panzarella MRF (Pompano)", "mrf", "Panzarella MRF", "1601 SW 3rd St, Pompano Beach, FL 33069",
       26.2310, -80.1450, "broward", ["bulky", "c_and_d", "drywall", "concrete", "yard"], _hours(), None, WALK_IN, None,
       "Quotes at the gate."),
    _f("Envirocycle (Fort Lauderdale)", "c_and_d", "Envirocycle", "849 SW 21st Ter, Fort Lauderdale, FL 33312",
       26.1130, -80.1660, "broward", ["c_and_d", "drywall", "concrete"], _hours(), None, WALK_IN, None,
       "C&D only. Quotes at the gate."),
    _f("Monarch Hill Landfill (Pompano)", "landfill", "WM", "2700 Wiles Rd, Pompano Beach, FL 33073", 26.2960, -80.1660,
       "broward", list(MONARCH_FEES), _hours(("05:00", "17:00"), ("05:00", "14:00")), "+19549842016", ACCOUNT,
       MONARCH_FEES, "Account customers only. Scale house (954) 984-2016."),
    _f("Reuter Recycling of Florida (Pembroke Pines)", "mrf", "WM", "20701 Pembroke Rd, Pembroke Pines, FL 33029",
       25.9950, -80.4180, "broward", list(REUTER_FEES), _hours(("07:00", "17:00"), ("07:00", "14:00")),
       "+19544369500", ACCOUNT, REUTER_FEES, "Account customers only; no public drop-off."),
    _f("South Broward Waste-to-Energy (Davie)", "wte", "FCC Environmental Services",
       "4400 S State Rd 7, Davie, FL 33314", 26.0880, -80.2070, "broward", ["msw", "yard", "c_and_d"],
       _hours(("08:00", "15:30")), "+19545816606", ACCOUNT, None, "Contract customers only."),
    _f("WM Davie Transfer Station", "transfer_station", "WM", "2380 College Ave, Davie, FL 33317", 26.0790, -80.2350,
       "broward", ["msw"], _hours(), "+18009634776", ACCOUNT, None, "Broward overflow under contract only."),
    _f("Waste Connections Pembroke Park", "transfer_station", "Waste Connections",
       "1899 SW 31st Ave, Pembroke Park, FL 33009", 25.9820, -80.1780, "broward", ["msw"], _hours(), None, ACCOUNT, None,
       "Contract customers only."),

    # ------------------------------------------------------------ Miami-Dade
    _f("Waste Connections Miami Transfer Station", "transfer_station", "Waste Connections",
       "3840 NW 37th Ct, Miami, FL 33142", 25.8110, -80.2560, "miami-dade",
       ["msw", "bulky", "mattress", "metal", "appliance_w_freon", "mixed", "c_and_d", "drywall", "concrete", "yard", "tires"],
       _hours(("08:00", "15:00"), ("08:00", "15:00")), "+13056383800", WALK_IN, None,
       "The one true walk-in in Dade: public and account, cash and all major cards. Untarped load is charged double."),
    _f("Waste Connections Opa-locka", "transfer_station", "Waste Connections",
       "3680 NW 135th St, Opa-locka, FL 33054", 25.8960, -80.2520, "miami-dade", ["c_and_d", "drywall", "concrete"],
       _hours(("06:00", "16:00"), ("06:00", "12:00")), "+13056383800", WALK_IN, None, "C&D, asphalt, fencing. Quotes at the gate."),
    _f("WM Recycling Hialeah", "c_and_d", "WM", "5000 NW 37th Ave, Hialeah, FL 33142", 25.8210, -80.2500, "miami-dade",
       ["c_and_d", "drywall", "yard"], _hours(("07:00", "17:00"), ("07:00", "12:00")), "+18552926719", WALK_IN, None,
       "Quotes at the gate."),
    _f("WM Recycling Miami", "c_and_d", "WM", "3401 NW 110th St, Miami, FL 33167", 25.8740, -80.2480, "miami-dade",
       ["c_and_d", "drywall", "concrete"], _hours(), "+18009634776", WALK_IN, None, "New C&D MRF. Quotes at the gate."),
    _f("North Dade Landfill", "landfill", "Miami-Dade DSWM", "21500 NW 47th Ave, Miami, FL 33055", 25.9740, -80.2680,
       "miami-dade", ["bulky", "mattress", "metal", "mixed", "c_and_d", "drywall", "concrete", "yard"],
       _hours(("07:00", "17:00"), ("07:00", "17:00"), ("07:00", "17:00")), "+13055146253", PERMIT,
       {k: v for k, v in MDC_LF_FEES.items() if k != "msw"},
       "Class III: no garbage. County hauler permit required. No cash — check, money order or card. $115.80/ton non-contract.",
       turnaround=30),
    _f("South Dade Landfill", "landfill", "Miami-Dade DSWM", "23707 SW 97th Ave, Homestead, FL 33032", 25.5320, -80.3490,
       "miami-dade", list(MDC_LF_FEES), _hours(("07:00", "17:00"), ("07:00", "17:00"), ("07:00", "17:00")),
       "+13052586949", PERMIT, MDC_LF_FEES,
       "Takes everything incl. garbage, tires, asbestos by appointment. County hauler permit required. No cash.",
       turnaround=30),
    _f("Miami-Dade Northeast Transfer Station", "transfer_station", "Miami-Dade DSWM",
       "18701 NE 6th Ave, Miami, FL 33179", 25.9470, -80.1930, "miami-dade", list(MDC_TS_FEES),
       _hours(("07:00", "17:00"), ("07:00", "17:00")), "+13055146666", PERMIT, MDC_TS_FEES,
       "Garbage and trash only. Rate includes the $17.30/ton transfer surcharge. Permit required, no cash."),
    _f("Miami-Dade Central Transfer Station", "transfer_station", "Miami-Dade DSWM",
       "1150 NW 20th St, Miami, FL 33127", 25.7950, -80.2130, "miami-dade", list(MDC_TS_FEES),
       _hours(("07:00", "17:00"), ("07:00", "17:00")), "+13055146666", PERMIT, MDC_TS_FEES,
       "Garbage and trash only. Rate includes the $17.30/ton transfer surcharge. Permit required, no cash."),
    _f("Miami-Dade West Transfer Station", "transfer_station", "Miami-Dade DSWM",
       "2900 SW 72nd Ave, Miami, FL 33155", 25.7450, -80.3120, "miami-dade", list(MDC_TS_FEES),
       _hours(("07:00", "17:00"), ("07:00", "17:00")), "+13055146666", PERMIT, MDC_TS_FEES,
       "Garbage and trash only. Rate includes the $17.30/ton transfer surcharge. Permit required, no cash."),
    _f("Medley Landfill", "landfill", "WM", "9350 NW 89th Ave, Medley, FL 33178", 25.8560, -80.3400, "miami-dade",
       list(MEDLEY_FEES), _hours(("05:00", "17:00"), ("05:00", "14:00")), "+18009634776", ACCOUNT, MEDLEY_FEES,
       "County and WM collection vehicles only. No public drop-off."),
]

MARTIN_FEES = {"msw": 75.60, "bulky": 53.60, "mattress": 53.60, "appliance_w_freon": 53.60, "mixed": 53.60,
               "c_and_d": 53.60, "drywall": 53.60, "concrete": 26.80, "metal": 26.80, "yard": 33.80, "tires": 151.30}
STLUCIE_FEES = {"msw": 79.0, "bulky": 79.0, "mattress": 79.0, "mixed": 79.0, "c_and_d": 69.0, "drywall": 69.0,
                "concrete": 69.0, "yard": 69.0, "tires": 150.0, "metal": 79.0, "appliance_w_freon": 79.0}
IRC_FEES = {"msw": 53.90, "bulky": 53.90, "mattress": 53.90, "mixed": 53.90, "c_and_d": 52.74, "drywall": 52.74,
            "concrete": 17.77, "yard": 49.75, "tires": 177.68, "metal": 0.0, "appliance_w_freon": 0.0}
BREVARD_FEES = {"msw": 36.42, "bulky": 36.42, "mattress": 36.42, "mixed": 38.47, "c_and_d": 38.47, "drywall": 38.47,
                "concrete": 38.47, "yard": 49.38, "tires": 190.68, "metal": 36.42, "appliance_w_freon": 36.42}

FACILITIES += [
    # ------------------------------------------------------------ Martin
    _f("Martin County Transfer & Recycling Facility (Palm City)", "transfer_station", "Martin County",
       "9101 SW Busch St, Palm City, FL 34990", 27.1375, -80.3060, "martin", list(MARTIN_FEES),
       _hours(("08:00", "17:00"), ("08:00", "12:00")), "+17724196967", WALK_IN, MARTIN_FEES,
       "Self-haul welcome. Weigh in by 4:45 (Sat 11:45). $6 minimum. Uncovered or after-hours loads billed double. "
       "Clean source-separated concrete/wood/metal is $26.80. Rates eff 10/1/2025.", turnaround=25),

    # ------------------------------------------------------------ St. Lucie
    _f("St. Lucie County Baling & Recycling Facility (Fort Pierce)", "landfill", "St. Lucie County",
       "6120 Glades Cut-Off Rd, Fort Pierce, FL 34981", 27.3960, -80.3900, "st-lucie", list(STLUCIE_FEES),
       _hours(("07:00", "17:00"), ("08:00", "12:00")), None, WALK_IN, STLUCIE_FEES,
       "Hand-unloaders must be on the scale by 4:15. $10 minimum. 1–5 car tires $5 each. Gate rates eff 2/1/2025.",
       turnaround=30),
    _f("East Coast Recycling (Fort Pierce)", "c_and_d", "East Coast Recycling", "4880 Glades Cut-Off Rd, Fort Pierce, FL 34981",
       27.4050, -80.3850, "st-lucie", ["yard", "concrete", "c_and_d"], _hours(), None, WALK_IN, None,
       "Yard waste, land clearing, pallets, clean concrete. Open to the public. Quotes at the gate."),

    # ------------------------------------------------------------ Indian River
    _f("Indian River County Landfill (Vero Beach)", "landfill", "Indian River County SWDD",
       "1325 74th Ave SW, Vero Beach, FL 32968", 27.6210, -80.4850, "indian-river", list(IRC_FEES),
       _hours(("07:00", "17:00"), ("07:00", "17:00"), ("07:00", "17:00")), "+17722263212", WALK_IN, IRC_FEES,
       "Open 7 days. Yard trash under 3 in. and scrap metal / white goods are FREE; clean concrete $17.77. "
       "C&D minimum $11.85. Uncovered load $118.45. Rates eff 10/1/2025.", turnaround=30),

    # ------------------------------------------------------------ Brevard
    _f("Brevard County Central Disposal Facility (Cocoa)", "landfill", "Brevard County",
       "2250 Adamson Rd, Cocoa, FL 32926", 28.3830, -80.7960, "brevard", list(BREVARD_FEES),
       _hours(("07:30", "17:30"), ("07:30", "17:30")), "+13216331888", WALK_IN, BREVARD_FEES,
       "Class I: takes everything. Rates per FDEP 2025 county survey (county gate sheet not public online) — confirm at the scale.",
       turnaround=30),
    _f("Brevard County Sarno Road Landfill & Transfer Station (Melbourne)", "landfill", "Brevard County",
       "3379 Sarno Rd, Melbourne, FL 32935", 28.1155, -80.6600, "brevard", list(BREVARD_FEES),
       _hours(("07:30", "17:30"), ("07:30", "17:30")), "+13216331888", WALK_IN, BREVARD_FEES,
       "Class III landfill plus garbage transfer. Rates per FDEP 2025 survey — confirm at the scale.", turnaround=25),
    _f("Brevard County Titusville Transfer Station", "transfer_station", "Brevard County",
       "3600 South St, Titusville, FL 32780", 28.5735, -80.8380, "brevard", ["msw", "bulky", "mattress", "yard"],
       _hours(("07:30", "17:30"), ("07:30", "17:30")), "+13212645048", WALK_IN, {k: BREVARD_FEES[k] for k in ("msw", "bulky", "mattress", "yard")},
       "Being rebuilt through Aug 2026 — vegetation, concrete, metal and tires go to Cocoa until it reopens. Call first."),
    _f("Melbourne C&D Landfill (Florida Recyclers of Brevard)", "c_and_d", "Florida Recyclers of Brevard",
       "3351 Sarno Rd, Melbourne, FL 32934", 28.1150, -80.6580, "brevard", ["c_and_d", "drywall", "concrete", "yard"],
       _hours(("07:30", "17:30"), ("07:30", "14:00")), "+13212556625", WALK_IN, None, "Private C&D yard. Quotes at the gate."),
]

SWA_OUT_OF_COUNTY_RATE = 156.0   # garbage / trash / C&D from outside Palm Beach County
MIN_CHARGE = 10.0


def by_name():
    return {f["name"]: f for f in FACILITIES}


def seed_landfill_facilities(session, LandfillFacility, TipFee, generate_uuid):
    """Upsert every facility and its current fee rows. Returns rows touched."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    touched = 0
    for spec in FACILITIES:
        row = session.query(LandfillFacility).filter_by(name=spec["name"]).first()
        fields = {k: spec[k] for k in ("type", "operator", "address", "lat", "lon", "county",
                                        "accepts_categories", "hours_json", "phone", "notes", "avg_turnaround_min")}
        fields["scale_method"] = "per_ton"
        if hasattr(LandfillFacility, "access"):
            fields["access"] = spec["access"]
            fields["origin_county"] = spec["origin_county"]
        if row is None:
            row = LandfillFacility(id=generate_uuid(), name=spec["name"], **fields)
            session.add(row)
            session.flush()
            touched += 1
        else:
            changed = False
            for k, v in fields.items():
                if getattr(row, k) != v:
                    setattr(row, k, v)
                    changed = True
            touched += int(changed)
        for cat, amount in spec["fees"].items():
            current = (session.query(TipFee).filter_by(facility_id=row.id, category=cat, effective_to=None)
                       .order_by(TipFee.captured_at.desc()).first())
            if current is not None and abs(current.fee_amount - float(amount)) < 0.005:
                continue
            if current is not None:
                current.effective_to = now
            session.add(TipFee(id=generate_uuid(), facility_id=row.id, category=cat, fee_amount=float(amount),
                               fee_unit="per_ton", effective_from=now, source="seed", confidence=0.85, captured_at=now))
            touched += 1
    session.commit()
    return touched
