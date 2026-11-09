#!/usr/bin/env bash
# =============================================================================
# Kaggle GPU OCR Deployment & Orchestration Script
# Project: Hán–Việt Parallel Corpus (HVTT, TLTVN, TVLT2)
#
# Supports both flag syntax and subcommand syntax:
#   ./kaggle_ocr/deploy_to_kaggle.sh --stage-images   | stage-images
#   ./kaggle_ocr/deploy_to_kaggle.sh --push-dataset   | upload-dataset [dir]
#   ./kaggle_ocr/deploy_to_kaggle.sh --push-kernel    | push-kernel
#   ./kaggle_ocr/deploy_to_kaggle.sh --status         | status
#   ./kaggle_ocr/deploy_to_kaggle.sh --pull-output    | download-output [dir]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Default to /opt/homebrew/bin/kaggle as specified, falling back to PATH if needed
KAGGLE_BIN="${KAGGLE_BIN:-/opt/homebrew/bin/kaggle}"
if [[ ! -x "${KAGGLE_BIN}" ]] && command -v kaggle >/dev/null 2>&1; then
  KAGGLE_BIN="$(command -v kaggle)"
fi

STAGING_DIR="${STAGING_DIR:-/tmp/han_viet_kaggle_dataset}"
DEFAULT_OUTPUT_DIR="${PROJECT_ROOT}"

resolve_kaggle_username() {
  if [[ -n "${KAGGLE_USERNAME:-}" ]]; then
    echo "${KAGGLE_USERNAME}"
    return 0
  fi

  python3 - "${KAGGLE_BIN}" <<'PYEOF'
import json
import os
import re
import subprocess
import sys
from pathlib import Path

kaggle_bin = sys.argv[1] if len(sys.argv) > 1 else ""
username = ""

# 1. Try reading ~/.kaggle/kaggle.json
kaggle_json = Path(os.path.expanduser("~/.kaggle/kaggle.json"))
try:
    if kaggle_json.is_file():
        data = json.loads(kaggle_json.read_text(encoding="utf-8"))
        username = str(data.get("username") or "").strip()
except Exception:
    username = ""

# 2. Try `kaggle config view` if kaggle.json was not used
if not username and kaggle_bin and os.access(kaggle_bin, os.X_OK):
    try:
        proc = subprocess.run(
            [kaggle_bin, "config", "view"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        m = re.search(r"username:\s*([^\s\r\n]+)", proc.stdout or "")
        if m:
            candidate = m.group(1).strip()
            if candidate and candidate.lower() not in ("none", "-", "null"):
                username = candidate
    except Exception:
        pass

print(username if username else "khoa")
PYEOF
}

RESOLVED_USERNAME="$(resolve_kaggle_username)"
DATASET_NAME="han-viet-parallel-corpus-pages"
KERNEL_NAME="han-viet-parallel-corpus-ocr-pipeline"
DATASET_SLUG="${DATASET_SLUG:-${RESOLVED_USERNAME}/${DATASET_NAME}}"
KERNEL_SLUG="${KERNEL_SLUG:-${RESOLVED_USERNAME}/${KERNEL_NAME}}"

sync_metadata_ids() {
  python3 - "${SCRIPT_DIR}" "${DATASET_SLUG}" "${KERNEL_SLUG}" <<'PYEOF'
import json
import sys
from pathlib import Path

script_dir = Path(sys.argv[1])
dataset_slug = sys.argv[2]
kernel_slug = sys.argv[3]

ds_meta_path = script_dir / "dataset-metadata.json"
if ds_meta_path.is_file():
    ds_meta = json.loads(ds_meta_path.read_text(encoding="utf-8"))
    ds_meta["id"] = dataset_slug
    ds_meta_path.write_text(json.dumps(ds_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

kn_meta_path = script_dir / "kernel-metadata.json"
if kn_meta_path.is_file():
    kn_meta = json.loads(kn_meta_path.read_text(encoding="utf-8"))
    kn_meta["id"] = kernel_slug
    kn_meta["dataset_sources"] = [dataset_slug]
    kn_meta["enable_gpu"] = True
    kn_meta["enable_internet"] = True
    kn_meta_path.write_text(json.dumps(kn_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PYEOF
}

check_kaggle_cli() {
  if [[ ! -x "${KAGGLE_BIN}" ]]; then
    echo "[ERROR] Kaggle CLI binary not found at ${KAGGLE_BIN}." >&2
    echo "        Install via: pip install kaggle  or  brew install kaggle" >&2
    exit 1
  fi
}

cmd_stage_images() {
  local staging_target="${1:-${STAGING_DIR}}"
  local mode="${2:-all}"
  sync_metadata_ids

  echo "=== Staging Corpus Images (${mode}) via Hardlinks into ${staging_target} ==="
  echo "Resolved Kaggle Username : ${RESOLVED_USERNAME}"
  echo "Dataset ID               : ${DATASET_SLUG}"
  echo "Kernel ID                : ${KERNEL_SLUG}"

  python3 - "${PROJECT_ROOT}" "${SCRIPT_DIR}" "${staging_target}" "${mode}" <<'PYEOF'
import json
import os
import shutil
import sys
import time
from pathlib import Path

t0 = time.perf_counter()
project_root = Path(sys.argv[1])
script_dir = Path(sys.argv[2])
staging_dir = Path(sys.argv[3])
mode = sys.argv[4] if len(sys.argv) > 4 else "all"

books = (
    ("HVTT", "HVTT_HanVanTinhTuy"),
    ("TVLT2", "TVLT2_ThoVanLyTran2"),
    ("TLTVN", "TLTVN_TheLoaiTuVN"),
)

if staging_dir.exists():
    shutil.rmtree(staging_dir)
staging_dir.mkdir(parents=True, exist_ok=True)

# 1. Copy dataset-metadata.json into staging root
shutil.copy2(script_dir / "dataset-metadata.json", staging_dir / "dataset-metadata.json")

# 2. Copy config/book_manifest.json if present
manifest_src = project_root / "config" / "book_manifest.json"
manifest_data = {}
if manifest_src.is_file():
    manifest_data = json.loads(manifest_src.read_text(encoding="utf-8"))
    (staging_dir / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_src, staging_dir / "config" / "book_manifest.json")
    shutil.copy2(manifest_src, staging_dir / "book_manifest.json")

# 3. Hardlink *.png files from deliverables/<book>/01_nguon/*.png
total_linked = 0
total_bytes = 0
per_book_counts = {}

for book_key, book_folder in books:
    src_dir = project_root / "deliverables" / book_folder / "01_nguon"
    dst_dir = staging_dir / "deliverables" / book_folder / "01_nguon"
    dst_dir.mkdir(parents=True, exist_ok=True)

    pilot_set = None
    if mode == "pilot" and "books" in manifest_data and book_key in manifest_data["books"]:
        pilot_set = {f"{int(p):04d}.png" for p in manifest_data["books"][book_key].get("pilot_pages", [])}

    count = 0
    if src_dir.is_dir():
        for png_file in sorted(src_dir.glob("*.png")):
            if pilot_set is not None and png_file.name not in pilot_set:
                continue
            dst_file = dst_dir / png_file.name
            try:
                os.link(png_file, dst_file)
            except OSError:
                shutil.copy2(png_file, dst_file)
            count += 1
            total_bytes += png_file.stat().st_size
    per_book_counts[book_folder] = count
    total_linked += count

elapsed = time.perf_counter() - t0
for book_folder, cnt in per_book_counts.items():
    print(f"  - {book_folder}: {cnt} PNG page(s) hardlinked")
print(f"Total staged: {total_linked} image(s) ({total_bytes / (1024*1024):.2f} MB payload) in {elapsed:.3f}s")
PYEOF
}

cmd_status() {
  check_kaggle_cli
  sync_metadata_ids
  echo "=== Kaggle CLI & Configuration ==="
  echo "Binary   : ${KAGGLE_BIN}"
  echo "Username : ${RESOLVED_USERNAME}"
  echo "Dataset  : ${DATASET_SLUG}"
  echo "Kernel   : ${KERNEL_SLUG}"
  "${KAGGLE_BIN}" --version || true
  echo ""
  echo "=== Dataset Status (${DATASET_SLUG}) ==="
  "${KAGGLE_BIN}" datasets status "${DATASET_SLUG}" || true
  echo ""
  echo "=== Kernel Status (${KERNEL_SLUG}) ==="
  "${KAGGLE_BIN}" kernels status "${KERNEL_SLUG}" || true
}

cmd_upload_dataset() {
  check_kaggle_cli
  sync_metadata_ids
  local target_dir="${1:-${STAGING_DIR}}"
  if [[ "${target_dir}" == "${STAGING_DIR}" ]] && [[ ! -f "${STAGING_DIR}/dataset-metadata.json" ]]; then
    cmd_stage_images "${STAGING_DIR}"
  else
    mkdir -p "${target_dir}"
    cp "${SCRIPT_DIR}/dataset-metadata.json" "${target_dir}/dataset-metadata.json"
  fi

  echo "=== Uploading/Updating Kaggle Dataset (${DATASET_SLUG}) from ${target_dir} ==="
  if "${KAGGLE_BIN}" datasets status "${DATASET_SLUG}" >/dev/null 2>&1; then
    "${KAGGLE_BIN}" datasets version -p "${target_dir}" -m "Update rendered 300 DPI page images" --dir-mode zip
  else
    "${KAGGLE_BIN}" datasets create -p "${target_dir}" --dir-mode zip
  fi
}

cmd_push_kernel() {
  check_kaggle_cli
  sync_metadata_ids
  echo "=== Pushing GPU OCR Kernel (${KERNEL_SLUG}) from ${SCRIPT_DIR} ==="
  "${KAGGLE_BIN}" kernels push -p "${SCRIPT_DIR}"
  echo ""
  echo "Kernel pushed! Monitor status with:"
  echo "  ${0} --status"
}

cmd_download_output() {
  check_kaggle_cli
  sync_metadata_ids
  local out_dir="${1:-${DEFAULT_OUTPUT_DIR}}"
  mkdir -p "${out_dir}"
  echo "=== Downloading Kernel Output (${KERNEL_SLUG}) to ${out_dir} ==="
  "${KAGGLE_BIN}" kernels output "${KERNEL_SLUG}" -p "${out_dir}"
  echo "Downloaded raw OCR outputs into: ${out_dir}/deliverables/*/02_ocr_tho/{han,viet}/"
}

cmd_help() {
  cat <<EOF
Usage: $(basename "$0") <command|flag> [args]

Commands & Flags:
  --stage-images | stage-images [staging_dir]
      Create /tmp/han_viet_kaggle_dataset, copy config/book_manifest.json,
      hardlink deliverables/*/01_nguon/*.png (0 MB extra disk), and sync
      Kaggle username in dataset-metadata.json & kernel-metadata.json.

  --push-dataset | upload-dataset [dataset_dir]
      Create or update the Kaggle dataset from /tmp/han_viet_kaggle_dataset.

  --push-kernel  | push-kernel
      Push kaggle_ocr/ocr_pipeline_kaggle.py to Kaggle GPU.

  --status       | status
      Check Kaggle CLI version, dataset status, and GPU kernel execution status.

  --pull-output  | download-output [output_dir]
      Download deliverables/*/02_ocr_tho/{han,viet}/*.json and ocr_results.jsonl.

  --help         | help
      Show this usage message.
EOF
}

if [[ $# -eq 0 ]]; then
  cmd_help
  exit 0
fi

while [[ $# -gt 0 ]]; do
  ACTION="$1"
  shift || true

  case "${ACTION}" in
    --stage-pilot|stage-pilot)
      cmd_stage_images "${STAGING_DIR}" "pilot"
      ;;
    --stage-images|stage-images)
      if [[ $# -gt 0 ]] && [[ "$1" != --* ]]; then
        cmd_stage_images "$1" "all"
        shift
      else
        cmd_stage_images "${STAGING_DIR}" "all"
      fi
      ;;
    --push-dataset|--upload-dataset|upload-dataset|push-dataset)
      if [[ $# -gt 0 ]] && [[ "$1" != --* ]]; then
        cmd_upload_dataset "$1"
        shift
      else
        cmd_upload_dataset
      fi
      ;;
    --push-kernel|push-kernel)
      cmd_push_kernel
      ;;
    --status|status)
      cmd_status
      ;;
    --pull-output|--download-output|download-output|pull-output)
      if [[ $# -gt 0 ]] && [[ "$1" != --* ]]; then
        cmd_download_output "$1"
        shift
      else
        cmd_download_output
      fi
      ;;
    help|--help|-h)
      cmd_help
      ;;
    *)
      echo "[ERROR] Unknown command or flag: ${ACTION}" >&2
      cmd_help >&2
      exit 1
      ;;
  esac
done
