"""Read-only independent pinned-wheel ownership check; no package/tool imports."""
from pathlib import Path
import hashlib
import json
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
TOOLCHAIN = HERE.parents[1] / "toolchain_v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    artifacts = json.loads((TOOLCHAIN / "python_artifacts.json").read_text())["artifacts"]
    inventory = json.loads((TOOLCHAIN / "slither_inventory.json").read_text())
    site = ROOT / inventory["python_env"] / "lib/python3.12/site-packages"
    owners = {}
    excluded = []
    for artifact in artifacts:
        wheel = ROOT / artifact["local_path"]
        if sha(wheel) != artifact["artifact_sha256"]:
            raise ValueError("Pinned wheel hash mismatch")
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                parts = Path(name).parts
                if name.endswith(".dist-info/RECORD") or name.endswith(".pyc"):
                    excluded.append({"package": artifact["package"], "member": name, "reason": "installer_record_or_cache"})
                    continue
                if parts[0].endswith(".data"):
                    if len(parts) > 2 and parts[1] in {"purelib", "platlib"}:
                        relative = Path(*parts[2:]).as_posix()
                    else:
                        excluded.append({"package": artifact["package"], "member": name, "reason": "installer_relocation"})
                        continue
                else:
                    relative = name
                owners.setdefault(relative, []).append({"package": artifact["package"], "version": artifact["version"],
                    "wheel_sha256": artifact["artifact_sha256"], "member": name,
                    "member_sha256": hashlib.sha256(archive.read(name)).hexdigest()})
    collisions, mismatches = [], []
    for relative, candidates in sorted(owners.items()):
        installed = site / relative
        actual = sha(installed) if installed.is_file() else None
        matches = [x["package"] for x in candidates if x["member_sha256"] == actual]
        row = {"relative_path": relative, "actual_sha256": actual, "matching_pinned_owners": matches, "owners": candidates}
        if len(candidates) > 1:
            collisions.append(row)
        if not matches:
            mismatches.append(row)
    result = {"schema": "independent_pinned_wheel_ownership_audit_v1", "tool_executions": 0,
              "source_sha256": sha(__file__), "python_artifacts_sha256": sha(TOOLCHAIN / "python_artifacts.json"),
              "wheels": len(artifacts), "installed_paths_checked": len(owners), "overlapping_paths": len(collisions),
              "different_bytes_overlapping_paths": sum(len({x["member_sha256"] for x in row["owners"]}) > 1 for row in collisions),
              "unmatched_paths": len(mismatches), "collisions": collisions, "mismatches": mismatches,
              "declared_installer_exclusions": excluded, "status": "pass" if not mismatches else "fail"}
    out = HERE / "WHEEL_COLLISION_AUDIT.json"
    with out.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("status", "wheels", "installed_paths_checked", "overlapping_paths", "different_bytes_overlapping_paths", "unmatched_paths")}))


if __name__ == "__main__":
    main()
