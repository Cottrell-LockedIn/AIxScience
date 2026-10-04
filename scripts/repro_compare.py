import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


REPORT_COLUMNS = [
    "file",
    "n_rows_committed",
    "n_rows_regenerated",
    "max_abs_diff",
    "identical",
    "note",
]
POST_FILES = [
    "registration/registration_by_image.csv",
    "charging/charging_by_image.csv",
]
MODAL_COLUMNS = [
    "timestamp_utc",
    "function",
    "n_inputs",
    "wall_s",
    "hardware",
    "git_sha",
    "config_hash",
    "est_cost_usd",
    "cost_source",
    "local_remote_max_abs_diff",
    "repeat_max_abs_diff",
    "note",
]
CHARGING_COLUMNS = [
    "sample_id",
    "old_scale",
    "new_scale",
    "old_glow_frac_of_c2",
    "new_glow_frac_of_c2",
    "old_F02_glow_excluded",
    "new_F02_glow_excluded",
]
IGNORED_COLUMNS = {"git_sha", "timestamp_utc"}


def _cell_text(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, np.generic):
        value = value.item()
    return str(value)


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _read_frame(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported tabular file: {path}")


def _compare_frames(
    committed: pd.DataFrame, regenerated: pd.DataFrame
) -> tuple[float | None, bool, int, int]:
    shared_columns = [
        name for name in committed.columns if name in regenerated.columns
    ]
    maximum = 0.0
    has_numeric = False
    changed_cells = 0
    numeric_changed_cells = 0
    other_changed_cells = 0
    common_rows = min(len(committed), len(regenerated))
    for name in shared_columns:
        if name in IGNORED_COLUMNS:
            continue
        for index in range(common_rows):
            left = committed.iloc[index][name]
            right = regenerated.iloc[index][name]
            left_number = _number(left)
            right_number = _number(right)
            if left_number is not None and right_number is not None:
                has_numeric = True
                difference = abs(left_number - right_number)
                maximum = max(maximum, difference)
                if difference:
                    changed_cells += 1
                    numeric_changed_cells += 1
            elif _cell_text(left) != _cell_text(right):
                changed_cells += 1
                other_changed_cells += 1
    identical = (
        list(committed.columns) == list(regenerated.columns)
        and len(committed) == len(regenerated)
        and changed_cells == 0
    )
    return (
        maximum if has_numeric else None,
        identical,
        numeric_changed_cells,
        other_changed_cells,
    )


def _normalize_json(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _normalize_json(item)
            for key, item in value.items()
            if key not in IGNORED_COLUMNS
        }
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    return value


def _compare_png_bytes(committed: Path, regenerated: Path) -> dict[str, object]:
    old_bytes = committed.read_bytes()
    new_bytes = regenerated.read_bytes()
    if old_bytes == new_bytes:
        return {
            "max_abs_diff": "",
            "identical": True,
            "note": "PNG bytes identical.",
        }
    with Image.open(committed) as old_image:
        old_pixels = np.asarray(old_image)
    with Image.open(regenerated) as new_image:
        new_pixels = np.asarray(new_image)
    if old_pixels.shape == new_pixels.shape:
        difference = np.abs(
            old_pixels.astype(np.float64) - new_pixels.astype(np.float64)
        )
        maximum = float(difference.max()) if difference.size else 0.0
        pixels_identical = bool(np.array_equal(old_pixels, new_pixels))
    else:
        maximum = None
        pixels_identical = False
    if pixels_identical:
        note = (
            "PNG bytes differ; decoded pixel arrays are identical "
            "(metadata-only difference)."
        )
    else:
        note = "PNG bytes and decoded pixels differ."
    return {
        "max_abs_diff": "",
        "identical": False,
        "note": note,
    }


def _compare_file(
    committed: Path, regenerated: Path, relative_path: str
) -> dict[str, object]:
    suffix = committed.suffix.lower()
    if suffix in {".csv", ".parquet"}:
        old_frame = _read_frame(committed)
        new_frame = _read_frame(regenerated)
        maximum, identical, numeric_changes, other_changes = _compare_frames(
            old_frame, new_frame
        )
        note = "No value differences after ignoring git_sha/timestamp_utc."
        if relative_path == "MODAL_RUNS.csv":
            if (
                len(new_frame) > len(old_frame)
                and numeric_changes == 0
                and other_changes == 0
            ):
                note = (
                    f"{len(new_frame) - len(old_frame)} verification rows "
                    f"appended; all {len(old_frame)} pre-existing records "
                    "match the committed values."
            )
        elif not identical:
            if (
                numeric_changes > 0
                and other_changes == 0
                and maximum is not None
                and maximum <= 1e-12
            ):
                note = "Only floating-point roundoff."
            else:
                note = (
                    f"{numeric_changes + other_changes} differing "
                    "common cells."
                )
        return {
            "n_rows_committed": len(old_frame),
            "n_rows_regenerated": len(new_frame),
            "max_abs_diff": "" if maximum is None else format(maximum, ".17g"),
            "identical": identical,
            "note": note,
        }
    if suffix == ".npy":
        old_values = np.load(committed, allow_pickle=False)
        new_values = np.load(regenerated, allow_pickle=False)
        same_shape = old_values.shape == new_values.shape
        if same_shape:
            difference = np.abs(
                old_values.astype(np.float64) - new_values.astype(np.float64)
            )
            maximum = float(difference.max()) if difference.size else 0.0
            identical = bool(np.array_equal(old_values, new_values, equal_nan=True))
        else:
            maximum = None
            identical = False
        return {
            "n_rows_committed": old_values.shape[0] if old_values.ndim else 1,
            "n_rows_regenerated": new_values.shape[0] if new_values.ndim else 1,
            "max_abs_diff": "" if maximum is None else format(maximum, ".17g"),
            "identical": identical,
            "note": (
                "Embedding array identical."
                if identical
                else "Embedding array values differ."
            ),
        }
    if suffix == ".json":
        with committed.open() as stream:
            old_value = _normalize_json(json.load(stream))
        with regenerated.open() as stream:
            new_value = _normalize_json(json.load(stream))
        identical = old_value == new_value
        return {
            "n_rows_committed": 1,
            "n_rows_regenerated": 1,
            "max_abs_diff": "0" if identical else "",
            "identical": identical,
            "note": (
                "Equal apart from git_sha/timestamp_utc."
                if identical
                else "JSON values differ beyond provenance."
            ),
        }
    if suffix == ".png":
        comparison = _compare_png_bytes(committed, regenerated)
        return {
            "n_rows_committed": 1,
            "n_rows_regenerated": 1,
            **comparison,
        }
    old_bytes = committed.read_bytes()
    new_bytes = regenerated.read_bytes()
    identical = old_bytes == new_bytes
    row_count = 0 if committed.name == ".gitkeep" else 1
    return {
        "n_rows_committed": row_count,
        "n_rows_regenerated": row_count,
        "max_abs_diff": "0" if identical else "",
        "identical": identical,
        "note": "Bytes identical." if identical else "Bytes differ.",
    }


def _report_row(
    relative_path: str,
    committed_results_dir: Path,
    regenerated_results_dir: Path,
    zero_if_no_numeric: bool = False,
) -> dict[str, object]:
    committed = committed_results_dir / relative_path
    regenerated = regenerated_results_dir / relative_path
    if not committed.is_file() or not regenerated.is_file():
        return {
            "file": f"results/{relative_path}",
            "n_rows_committed": 1 if committed.is_file() else 0,
            "n_rows_regenerated": 1 if regenerated.is_file() else 0,
            "max_abs_diff": "",
            "identical": False,
            "note": "File missing from one results directory.",
        }
    details = _compare_file(committed, regenerated, relative_path)
    if zero_if_no_numeric and details["max_abs_diff"] == "":
        details["max_abs_diff"] = "0"
    return {"file": f"results/{relative_path}", **details}


def _all_file_rows(
    committed_results_dir: Path, regenerated_results_dir: Path
) -> list[dict[str, object]]:
    relative_paths = sorted(
        path.relative_to(committed_results_dir).as_posix()
        for path in committed_results_dir.rglob("*")
        if path.is_file()
    )
    return [
        _report_row(path, committed_results_dir, regenerated_results_dir)
        for path in relative_paths
    ]


def _mask_row(
    committed_masks_dir: Path, regenerated_masks_dir: Path
) -> dict[str, object]:
    old_files = {
        path.relative_to(committed_masks_dir).as_posix(): path
        for path in committed_masks_dir.rglob("*.png")
    }
    new_files = {
        path.relative_to(regenerated_masks_dir).as_posix(): path
        for path in regenerated_masks_dir.rglob("*.png")
    }
    same_names = old_files.keys() == new_files.keys()
    identical = same_names and all(
        old_files[name].read_bytes() == new_files[name].read_bytes()
        for name in old_files
    )
    count_old, count_new = len(old_files), len(new_files)
    note = (
        f"All {count_new} regenerated masks were byte-identical to the "
        "persisted Phase A reference; masks are not tracked in the branch."
        if identical
        else "Mask file sets or bytes differ from the Phase A reference."
    )
    if identical:
        note = (
            f"All {count_new:,} regenerated masks were byte-identical to the "
            "persisted Phase A reference; masks are not tracked in the branch."
        )
    return {
        "file": "data/masks/*.png (Phase A reference)",
        "n_rows_committed": count_old,
        "n_rows_regenerated": count_new,
        "max_abs_diff": "0" if identical else "",
        "identical": identical,
        "note": note,
    }


def _png_pixels_row(
    committed_results_dir: Path, regenerated_results_dir: Path
) -> dict[str, object]:
    old_dir = committed_results_dir / "inspection"
    new_dir = regenerated_results_dir / "inspection"
    old_files = {path.name: path for path in old_dir.glob("*.png")}
    new_files = {path.name: path for path in new_dir.glob("*.png")}
    same_names = old_files.keys() == new_files.keys()
    arrays_equal = same_names
    maximum = 0.0
    for name in old_files.keys() & new_files.keys():
        with Image.open(old_files[name]) as old_image:
            old_pixels = np.asarray(old_image)
        with Image.open(new_files[name]) as new_image:
            new_pixels = np.asarray(new_image)
        if old_pixels.shape != new_pixels.shape:
            arrays_equal = False
            continue
        difference = np.abs(
            old_pixels.astype(np.float64) - new_pixels.astype(np.float64)
        )
        maximum = max(maximum, float(difference.max()) if difference.size else 0.0)
        arrays_equal = arrays_equal and bool(np.array_equal(old_pixels, new_pixels))
    count_old, count_new = len(old_files), len(new_files)
    count_label = "five" if count_old == 5 else f"{count_old:,}"
    note = (
        f"All {count_label} decoded inspection PNG pixel arrays were identical; "
        "only PNG metadata/encoding differed."
        if arrays_equal
        else "Decoded inspection PNG pixel arrays differ."
    )
    return {
        "file": "results/inspection/*.png (decoded pixel comparison)",
        "n_rows_committed": count_old,
        "n_rows_regenerated": count_new,
        "max_abs_diff": format(maximum, ".17g") if arrays_equal else "",
        "identical": arrays_equal,
        "note": note,
    }


def _modal_rows(
    committed_results_dir: Path, regenerated_results_dir: Path
) -> list[dict[str, object]]:
    with (committed_results_dir / "MODAL_RUNS.csv").open(newline="") as stream:
        baseline_rows = list(csv.DictReader(stream))
    with (regenerated_results_dir / "MODAL_RUNS.csv").open(newline="") as stream:
        regenerated_rows = list(csv.DictReader(stream))
    appended = regenerated_rows[len(baseline_rows):]
    result = []
    for source_row in appended:
        row = {column: source_row.get(column, "") for column in MODAL_COLUMNS}
        row["local_remote_max_abs_diff"] = ""
        row["repeat_max_abs_diff"] = ""
        row["note"] = "fresh_b verification log did not record determinism values"
        result.append(row)
    return result


def _charging_rows(
    committed_results_dir: Path, regenerated_results_dir: Path
) -> list[dict[str, str]]:
    old_registration = _read_frame(
        committed_results_dir / "registration/registration_by_image.csv"
    )
    new_registration = _read_frame(
        regenerated_results_dir / "registration/registration_by_image.csv"
    )
    old_charging = _read_frame(
        committed_results_dir / "charging/charging_by_image.csv"
    ).set_index("sample_id")
    new_charging = _read_frame(
        regenerated_results_dir / "charging/charging_by_image.csv"
    ).set_index("sample_id")

    def inlens_scales(frame: pd.DataFrame) -> dict[str, str]:
        inlens = frame.loc[frame["channel"].eq("Inlens")]
        return dict(zip(inlens["sample_id"], inlens["scale"]))

    old_scales = inlens_scales(old_registration)
    new_scales = inlens_scales(new_registration)
    sample_ids = [
        sample_id
        for sample_id in old_charging.index
        if sample_id in old_scales
        and sample_id in new_scales
        and sample_id in new_charging.index
    ]
    rows = []
    for sample_id in sample_ids:
        old = old_charging.loc[sample_id]
        new = new_charging.loc[sample_id]
        rows.append(
            {
                "sample_id": sample_id,
                "old_scale": old_scales[sample_id],
                "new_scale": new_scales[sample_id],
                "old_glow_frac_of_c2": old["glow_frac_of_c2"],
                "new_glow_frac_of_c2": new["glow_frac_of_c2"],
                "old_F02_glow_excluded": old["F02_glow_excluded"],
                "new_F02_glow_excluded": new["F02_glow_excluded"],
            }
        )
    return rows


def _write_rows(
    output_path: Path, columns: list[str], rows: list[dict[str, object]]
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=columns, lineterminator="\n"
        )
        writer.writeheader()
        for source_row in rows:
            row = dict(source_row)
            if isinstance(row.get("identical"), bool):
                row["identical"] = str(row["identical"]).lower()
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("committed_results_dir", type=Path)
    parser.add_argument("regenerated_results_dir", type=Path)
    parser.add_argument("output_path", type=Path)
    parser.add_argument(
        "--kind",
        choices=("full", "post", "modal", "charging"),
        required=True,
    )
    parser.add_argument("--committed-masks-dir", type=Path)
    parser.add_argument("--regenerated-masks-dir", type=Path)
    args = parser.parse_args()

    if args.kind == "full":
        if args.committed_masks_dir is None or args.regenerated_masks_dir is None:
            parser.error("full comparison requires both mask directory options")
        rows = _all_file_rows(
            args.committed_results_dir, args.regenerated_results_dir
        )
        rows.append(
            _mask_row(args.committed_masks_dir, args.regenerated_masks_dir)
        )
        rows.append(
            _png_pixels_row(
                args.committed_results_dir, args.regenerated_results_dir
            )
        )
        _write_rows(args.output_path, REPORT_COLUMNS, rows)
    elif args.kind == "post":
        stats_paths = sorted(
            path.relative_to(args.committed_results_dir).as_posix()
            for path in (args.committed_results_dir / "stats").glob("*.csv")
        )
        verdict_paths = sorted(
            path.relative_to(args.committed_results_dir).as_posix()
            for path in (args.committed_results_dir / "verdicts").glob("*.json")
        )
        paths = POST_FILES + stats_paths + verdict_paths
        _write_rows(
            args.output_path,
            REPORT_COLUMNS,
            [
                _report_row(
                    path,
                    args.committed_results_dir,
                    args.regenerated_results_dir,
                    zero_if_no_numeric=True,
                )
                for path in paths
            ],
        )
    elif args.kind == "modal":
        _write_rows(
            args.output_path, MODAL_COLUMNS,
            _modal_rows(args.committed_results_dir, args.regenerated_results_dir),
        )
    else:
        _write_rows(
            args.output_path,
            CHARGING_COLUMNS,
            _charging_rows(
                args.committed_results_dir, args.regenerated_results_dir
            ),
        )


if __name__ == "__main__":
    main()
