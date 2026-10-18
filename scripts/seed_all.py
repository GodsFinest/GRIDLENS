"""Master seed script for GridLens synthetic substation environment and COMTRADE datasets."""
import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.comtrade.generator import ComtradeGenerator


def seed_environment():
    print("============================================================")
    print("Seeding Orion Grid Substation OGS-01 Environment...")
    print("============================================================")

    comtrade_dir = os.path.abspath("data/comtrade")
    os.makedirs(comtrade_dir, exist_ok=True)

    # 1. Generate COMTRADE oscillography files for Incident A
    print("Generating Incident A COMTRADE files (INC-2026-001)...")
    res_a = ComtradeGenerator.generate_incident_a_files(comtrade_dir)
    print(f" -> Created {res_a['cfg']} and {res_a['dat']}")

    # 2. Generate COMTRADE oscillography files for Incident B
    print("Generating Incident B COMTRADE files (INC-2026-002)...")
    res_b = ComtradeGenerator.generate_incident_b_files(comtrade_dir)
    print(f" -> Created {res_b['cfg']} and {res_b['dat']}")

    # 3. Generate COMTRADE oscillography files for Incident C
    print("Generating Incident C COMTRADE files (INC-2026-003)...")
    res_c = ComtradeGenerator.generate_incident_c_files(comtrade_dir)
    print(f" -> Created {res_c['cfg']} and {res_c['dat']}")

    # 4. Generate COMTRADE oscillography files for Incident D
    print("Generating Incident D COMTRADE files (INC-2026-004)...")
    res_d = ComtradeGenerator.generate_incident_d_files(comtrade_dir)
    print(f" -> Created {res_d['cfg']} and {res_d['dat']}")

    # 5. Generate COMTRADE oscillography files for Incident E
    print("Generating Incident E COMTRADE files (INC-2026-005)...")
    res_e = ComtradeGenerator.generate_incident_e_files(comtrade_dir)
    print(f" -> Created {res_e['cfg']} and {res_e['dat']}")

    print("\nEnvironment seeded successfully with synthetic COMTRADE fixtures, topology, and technical documents.")
    print("============================================================")


if __name__ == "__main__":
    seed_environment()
