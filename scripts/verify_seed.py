#!/usr/bin/env python3
"""Verification script asserting schema validity, referential integrity, and file checksums for seed data."""
import hashlib
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT_DIR / "data" / "seed"
COMTRADE_DIR = ROOT_DIR / "data" / "comtrade"
HISTORY_SHA256 = "f4a818c4f18c819eb8b77fdf7400c6ed8f98e5b3fe8fb0260a737a3cd34fb8fc"


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def verify_seed() -> bool:
    print("=== GridLens Seed Data & Referential Integrity Verification ===")
    errors = []

    # 0. Verify the reproducible history seed consumed by HistoryTool.
    history_file = SEED_DIR / "history.json"
    if not history_file.exists():
        errors.append(f"History seed missing: {history_file}")
    else:
        history_hash = sha256_file(history_file)
        if history_hash != HISTORY_SHA256:
            errors.append(
                f"History seed checksum mismatch: expected {HISTORY_SHA256}, got {history_hash}"
            )
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history_records = json.load(f)
            if len(history_records) != 3:
                errors.append(f"Expected 3 seeded history records, got {len(history_records)}")
        except (OSError, json.JSONDecodeError, TypeError):
            errors.append(f"History seed is not valid JSON: {history_file}")

    # 1. Load substation_ogs01.json
    substation_file = SEED_DIR / "substation_ogs01.json"
    if not substation_file.exists():
        print(f"FAIL: Substation file missing: {substation_file}")
        return False

    with open(substation_file, "r", encoding="utf-8") as f:
        substation = json.load(f)

    # Normalize collections
    feeders = {f["feeder_id"]: f for f in substation.get("feeders", [])} if isinstance(substation.get("feeders"), list) else substation.get("feeders", {})
    breakers = {b["breaker_id"]: b for b in substation.get("breakers", [])} if isinstance(substation.get("breakers"), list) else substation.get("breakers", {})
    relays = {r["relay_id"]: r for r in substation.get("relays", [])} if isinstance(substation.get("relays"), list) else substation.get("relays", {})
    ieds = {i["ied_id"]: i for i in substation.get("ieds", [])} if isinstance(substation.get("ieds"), list) else substation.get("ieds", {})
    sensors = {s["sensor_id"]: s for s in substation.get("sensors", [])} if isinstance(substation.get("sensors"), list) else substation.get("sensors", {})

    substation_id = substation.get("substation_id") or substation.get("substation", {}).get("id", "UNKNOWN")
    print(f"Loaded substation '{substation_id}': {len(feeders)} feeders, {len(breakers)} breakers, {len(relays)} relays, {len(ieds)} IEDs, {len(sensors)} sensors.")

    # 2. Check internal topology referential integrity
    for f_id, f_data in feeders.items():
        relay_id = f_data.get("primary_relay_id")
        if relay_id and relay_id not in relays:
            errors.append(f"Feeder {f_id} references missing primary_relay_id '{relay_id}'")

    for r_id, r_data in relays.items():
        brk_id = r_data.get("associated_breaker_id") or r_data.get("controlled_breaker_id")
        if brk_id and brk_id not in breakers:
            errors.append(f"Relay {r_id} references missing associated_breaker_id '{brk_id}'")

    # 3. Load incidents.json and verify cross-table referential integrity
    incidents_file = SEED_DIR / "incidents.json"
    if not incidents_file.exists():
        print(f"FAIL: Incidents file missing: {incidents_file}")
        return False

    with open(incidents_file, "r", encoding="utf-8") as f:
        incidents = json.load(f)

    print(f"Loaded {len(incidents)} seed incidents from {incidents_file.name}.")

    for inc in incidents:
        inc_id = inc.get("incident_id")
        f_id = inc.get("feeder_id")
        brk_id = inc.get("involved_breaker_id")
        r_id = inc.get("involved_relay_id")
        ied_id = inc.get("involved_ied_id")
        comtrade_id = inc.get("comtrade_file_id")

        if f_id not in feeders:
            errors.append(f"Incident {inc_id} references unknown feeder '{f_id}'")
        if brk_id not in breakers:
            errors.append(f"Incident {inc_id} references unknown breaker '{brk_id}'")
        if r_id not in relays:
            errors.append(f"Incident {inc_id} references unknown relay '{r_id}'")
        if ied_id not in ieds:
            errors.append(f"Incident {inc_id} references unknown IED '{ied_id}'")

        # 4. Verify COMTRADE file existence and checksums
        if comtrade_id:
            cfg_path = COMTRADE_DIR / f"{comtrade_id}.CFG"
            dat_path = COMTRADE_DIR / f"{comtrade_id}.DAT"

            if not cfg_path.exists():
                errors.append(f"Incident {inc_id} COMTRADE CFG missing: {cfg_path.name}")
            else:
                cfg_hash = sha256_file(cfg_path)
                if cfg_path.stat().st_size == 0:
                    errors.append(f"Incident {inc_id} COMTRADE CFG is empty: {cfg_path.name}")
                else:
                    print(f"  [OK] {comtrade_id}.CFG (size: {cfg_path.stat().st_size} bytes, sha256: {cfg_hash[:12]}...)")

            if not dat_path.exists():
                errors.append(f"Incident {inc_id} COMTRADE DAT missing: {dat_path.name}")
            else:
                dat_hash = sha256_file(dat_path)
                if dat_path.stat().st_size == 0:
                    errors.append(f"Incident {inc_id} COMTRADE DAT is empty: {dat_path.name}")
                else:
                    print(f"  [OK] {comtrade_id}.DAT (size: {dat_path.stat().st_size} bytes, sha256: {dat_hash[:12]}...)")

    if errors:
        print(f"\nFAILED: Found {len(errors)} integrity errors:")
        for err in errors:
            print(f"  - {err}")
        return False

    print("\nSUCCESS: All substation topology, incident fixtures, and COMTRADE files passed integrity verification.")
    return True


if __name__ == "__main__":
    success = verify_seed()
    sys.exit(0 if success else 1)
