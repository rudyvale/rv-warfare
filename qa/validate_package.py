import argparse
import collections
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


def audit(archive_path):
    errors = []
    warnings = []
    mods = []
    hashes = {}
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        duplicates = [name for name, count in collections.Counter(n.casefold() for n in names).items() if count > 1]
        errors.extend("Duplicate archive entry: " + name for name in duplicates)
        for name in names:
            parts = name.replace("\\", "/").split("/")
            if name.startswith(("/", "\\")) or ".." in parts or ":" in name:
                errors.append("Unsafe archive path: " + name)
            if any(part.lower() in {"logs", "crash-reports", "patch-source", ".git"} for part in parts):
                errors.append("Private or development directory: " + name)
            if parts[-1].lower() in {"tlauncherprofiles.json", "launcher_accounts.json", "usercache.json"}:
                errors.append("Account data in package: " + name)
            if name.endswith("/"):
                continue
            data = archive.read(name)
            hashes[name] = hashlib.sha256(data).hexdigest()
            if name.lower().endswith(".jar") and "mods" in [part.lower() for part in parts]:
                with zipfile.ZipFile(io.BytesIO(data)) as jar:
                    if jar.testzip() is not None:
                        errors.append("Corrupt JAR: " + name)
                    mod_ids = []
                    if "mcmod.info" in jar.namelist():
                        try:
                            info = json.loads(jar.read("mcmod.info").decode("utf-8-sig"))
                            if isinstance(info, dict):
                                info = info.get("modList", [])
                            mod_ids = [entry["modid"] for entry in info if isinstance(entry, dict) and entry.get("modid")]
                        except (ValueError, UnicodeError, KeyError):
                            warnings.append("Non-JSON mcmod.info: " + name)
                    mods.append({"path": name, "ids": mod_ids})
            if name.lower().endswith((".ps1", ".cmd", ".md", ".txt", ".json", ".cfg", ".yml", ".xml")) and len(data) < 2_000_000:
                content = data.decode("utf-8-sig", errors="replace")
                if re.search(r"[A-Za-z]:[\\/]+Users[\\/]+User[\\/]", content, re.I):
                    errors.append("Author-specific absolute path: " + name)
                if "BACKUP_PATH" in content:
                    errors.append("Unexpanded template: " + name)
                if name.lower().endswith("options.txt") and re.search(r"^lastServer:.+", content, re.M):
                    warnings.append("Preselected server in options: " + name)
        ids = collections.defaultdict(list)
        for mod in mods:
            for mod_id in mod["ids"]:
                ids[mod_id].append(mod["path"])
        for mod_id, paths in ids.items():
            if len(paths) > 1:
                errors.append("Duplicate mod " + mod_id + ": " + ", ".join(paths))
        corrupt = archive.testzip()
        if corrupt:
            errors.append("Corrupt archive entry: " + corrupt)
    return {"archive": str(archive_path.resolve()), "bytes": archive_path.stat().st_size, "entries": len(names), "mods": mods, "errors": errors, "warnings": warnings, "sha256": hashlib.file_digest(archive_path.open("rb"), "sha256").hexdigest(), "file_hashes": hashes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.archive)
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "file_hashes"}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result["errors"]))


if __name__ == "__main__":
    main()
