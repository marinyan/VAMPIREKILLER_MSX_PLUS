"""Build one selected IPS and a reproducible, ROM-free build record."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import tempfile

from build_patches import apply_ips, ips_patch
from feature_catalog import resolve_selection
from patches import make_selected_rom

CONFIG_SCHEMA = 1


def selection_config(feature_ids):
    return {"schema": CONFIG_SCHEMA,
            "fixes": [fix.id for fix in resolve_selection(feature_ids)]}


def read_config(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if (not isinstance(data, dict) or set(data) != {"schema", "fixes"}
            or type(data["schema"]) is not int or data["schema"] != CONFIG_SCHEMA
            or not isinstance(data["fixes"], list)
            or not all(isinstance(value, str) for value in data["fixes"])):
        raise ValueError("Expected a selection config with schema=1 and a fixes list")
    return selection_config(data["fixes"])["fixes"]


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


@dataclass(frozen=True)
class Artifact:
    patch: bytes
    report: dict


def build_selection(source, feature_ids):
    config = selection_config(feature_ids)
    target, info, _, _ = make_selected_rom(source, config["fixes"])
    patch = ips_patch(source, target)
    if apply_ips(source, patch) != target:
        raise ValueError("Generated IPS did not reproduce the selected ROM")
    info["changes"] = [{key: value for key, value in change.items() if key not in ("before", "after")}
                       for change in info["changes"]]
    return Artifact(patch, dict(format="vampire-killer-ips-build-v1", selection=config,
                                ips_sha256=hashlib.sha256(patch).hexdigest(),
                                ips_bytes=len(patch), **info))


def artifact_files(artifact, output, config_output=None):
    output = Path(output)
    if output.suffix.lower() != ".ips":
        raise ValueError("The output file must have an .ips extension")
    files = {output: artifact.patch,
             Path(str(output) + ".json"): json_bytes(artifact.report)}
    if config_output is not None:
        config_output = Path(config_output)
        if config_output in files:
            raise ValueError("Config and IPS/report outputs must use different paths")
        files[config_output] = json_bytes(artifact.report["selection"])
    return files


def write_files(files, *, protected=(), overwrite=False):
    """Validate destinations and stage all bytes before writing output files."""
    resolved = [path.resolve() for path in files]
    if len(set(resolved)) != len(resolved):
        raise ValueError("Output files must use different paths")
    protected = {Path(path).resolve() for path in protected}
    for path in files:
        if path.resolve() in protected:
            raise ValueError(f"An output would replace an input file: {path.name}")
        if path.is_dir():
            raise ValueError(f"Output is a directory: {path}")
        if path.exists() and not overwrite:
            raise FileExistsError(f"Output already exists: {path}")
    staged = []
    try:
        for path, data in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temp = tempfile.mkstemp(prefix=".ips-build-", dir=path.parent)
            staged.append((Path(temp), path))
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
        for temp, path in staged:
            if overwrite:
                os.replace(temp, path)
            else:
                # An exclusive create also protects files appearing after preflight.
                with path.open("xb") as stream:
                    stream.write(temp.read_bytes())
    finally:
        for temp, _ in staged:
            temp.unlink(missing_ok=True)
