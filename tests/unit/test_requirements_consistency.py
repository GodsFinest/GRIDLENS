"""Keep the runtime requirements compatible with the pinned CI environment."""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?:\[[^]]+\])?(?P<operator>==|>=|<=|>|<)(?P<version>[0-9]+(?:\.[0-9]+)*)$"
)


def _requirements(path: Path):
    parsed = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = REQUIREMENT_RE.fullmatch(line)
        assert match, f"Unsupported requirement syntax in {path.name}: {line}"
        parsed.setdefault(match["name"].lower(), []).append(
            (match["operator"], tuple(int(part) for part in match["version"].split(".")))
        )
    return parsed


def test_ci_pins_satisfy_shared_runtime_requirements():
    runtime = _requirements(ROOT / "requirements.txt")
    ci = _requirements(ROOT / "requirements-ci.txt")

    for package, ci_specs in ci.items():
        if package not in runtime:
            continue
        assert len(ci_specs) == 1 and ci_specs[0][0] == "==", f"CI must pin {package} exactly"
        ci_version = ci_specs[0][1]
        for operator, runtime_version in runtime[package]:
            if operator == ">=":
                assert ci_version >= runtime_version, f"CI pin for {package} is below runtime minimum"
            elif operator == "<=":
                assert ci_version <= runtime_version, f"CI pin for {package} exceeds runtime maximum"
            elif operator == ">":
                assert ci_version > runtime_version, f"CI pin for {package} does not exceed runtime minimum"
            elif operator == "<":
                assert ci_version < runtime_version, f"CI pin for {package} exceeds runtime maximum"
            elif operator == "==":
                assert ci_version == runtime_version, f"CI pin for {package} conflicts with runtime pin"
