#!/usr/bin/env python3

import os
import shutil
import subprocess
import zipfile
import tarfile
import tempfile
import natsort

from utils import Style, print_error, print_info, print_success, print_header_line

def check_command_exists(command):
    return shutil.which(command) is not None

def natural_sort_key(s, _nsre=natsort.natsort_keygen()):
    return _nsre(s)

def create_cbz_from_images(image_folder, cbz_output_path):
    print(f"  {Style.CYAN}Creating CBZ:{Style.RESET} {os.path.basename(cbz_output_path)}")
    try:
        images = sorted(
            [os.path.join(image_folder, f) for f in os.listdir(image_folder)
             if os.path.isfile(os.path.join(image_folder, f)) and
             f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.jxl'))],
            key=natural_sort_key
        )
        if not images:
            print_error(f"    No compatible image files found in {image_folder}.")
            return False

        with zipfile.ZipFile(cbz_output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, image_path in enumerate(images):
                _, ext = os.path.splitext(image_path)
                archive_image_name = f"page_{i+1:04d}{ext}"
                zf.write(image_path, arcname=archive_image_name)
        print_success(f"  Successfully created {os.path.basename(cbz_output_path)}")
        return True
    except Exception as e:
        print_error(f"    Failed to create CBZ {os.path.basename(cbz_output_path)}: {e}")
        return False

def _extract_zip_for_cbr_fallback(archive_path, temp_extract_dir):
    print(f"    {Style.BRIGHT_BLACK}Attempting to extract as ZIP...{Style.RESET}")
    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            image_members = [m for m in zf.infolist() if not m.is_dir() and os.path.splitext(m.filename)[1].lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.jxl')]
            if not image_members:
                print_error(f"    No images found in {os.path.basename(archive_path)} when treated as ZIP.")
                return False
            zf.extractall(path=temp_extract_dir, members=image_members)
        return True
    except Exception as e:
        print_error(f"    Error extracting as ZIP: {e}")
        return False

def convert_cbr_to_cbz(cbr_path, output_dir):
    base_name = os.path.splitext(os.path.basename(cbr_path))[0]
    cbz_output_path = os.path.join(output_dir, f"{base_name}.cbz")
    if os.path.exists(cbz_output_path):
        print_info(f"  Skipping CBR, CBZ already exists: {os.path.basename(cbz_output_path)}")
        return True, cbz_output_path

    print(f"  {Style.CYAN}Converting CBR-like file:{Style.RESET} {os.path.basename(cbr_path)}")
    with tempfile.TemporaryDirectory() as temp_dir:
        extracted = False
        if check_command_exists("unrar"):
            cmd = ["unrar", "e", "-o+", "-y", cbr_path, temp_dir + os.sep]
            proc = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
            if proc.returncode == 0:
                extracted = True
            elif "is not RAR archive" in proc.stderr or "is not RAR archive" in proc.stdout:
                extracted = _extract_zip_for_cbr_fallback(cbr_path, temp_dir)
            else:
                print_error(f"    unrar failed (code {proc.returncode}): {proc.stderr.strip()}")
        else:
            print_info("  `unrar` not found. Attempting to treat .cbr as .zip.")
            extracted = _extract_zip_for_cbr_fallback(cbr_path, temp_dir)

        if extracted and create_cbz_from_images(temp_dir, cbz_output_path):
            return True, cbz_output_path
    print_error(f"    Could not convert {os.path.basename(cbr_path)}.")
    return False, None

def convert_cb7_to_cbz(cb7_path, output_dir):
    if not check_command_exists("7z"):
        print_error("`7z` not found. Cannot convert CB7 files.")
        return False, None
    base_name = os.path.splitext(os.path.basename(cb7_path))[0]
    cbz_output_path = os.path.join(output_dir, f"{base_name}.cbz")
    if os.path.exists(cbz_output_path):
        print_info(f"  Skipping CB7, CBZ already exists: {os.path.basename(cbz_output_path)}")
        return True, cbz_output_path

    print_info(f"  Converting CB7: {os.path.basename(cb7_path)}")
    with tempfile.TemporaryDirectory() as temp_dir:
        cmd = ["7z", "x", cb7_path, f"-o{temp_dir}", "-y"]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            print_error(f"    7z failed: {proc.stderr.decode(errors='ignore').strip()}")
            return False, None
        if create_cbz_from_images(temp_dir, cbz_output_path):
            return True, cbz_output_path
    return False, None

def convert_cbt_to_cbz(cbt_path, output_dir):
    base_name = os.path.splitext(os.path.basename(cbt_path))[0]
    cbz_output_path = os.path.join(output_dir, f"{base_name}.cbz")
    if os.path.exists(cbz_output_path):
        print_info(f"  Skipping CBT, CBZ already exists: {os.path.basename(cbz_output_path)}")
        return True, cbz_output_path

    print_info(f"  Converting CBT: {os.path.basename(cbt_path)}")
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            with tarfile.open(cbt_path, 'r:*') as tar:
                members = [m for m in tar.getmembers() if m.isfile() and m.name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.jxl'))]
                if not members:
                    print_error(f"    No images found in CBT: {os.path.basename(cbt_path)}")
                    return False, None
                tar.extractall(path=temp_dir, members=members)
            if create_cbz_from_images(temp_dir, cbz_output_path):
                return True, cbz_output_path
        except Exception as e:
            print_error(f"    Error during CBT conversion: {e}")
    return False, None

def convert_pdf_to_cbz(pdf_path, output_dir):
    if not check_command_exists("mutool"):
        print_error("`mutool` not found. Cannot convert PDF files.")
        return False, None
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    cbz_output_path = os.path.join(output_dir, f"{base_name}.cbz")
    if os.path.exists(cbz_output_path):
        print_info(f"  Skipping PDF, CBZ already exists: {os.path.basename(cbz_output_path)}")
        return True, cbz_output_path

    print_info(f"  Converting PDF: {os.path.basename(pdf_path)}")
    with tempfile.TemporaryDirectory() as temp_dir:
        output_pattern = os.path.join(temp_dir, "page-%04d.png")
        cmd = ["mutool", "draw", "-o", output_pattern, "-r", "150", pdf_path]
        proc = subprocess.run(cmd, capture_output=True)
        if not any(f.lower().endswith(".png") for f in os.listdir(temp_dir)):
            print_error(f"    mutool failed or extracted no images: {proc.stderr.decode(errors='ignore').strip()}")
            return False, None
        if create_cbz_from_images(temp_dir, cbz_output_path):
            return True, cbz_output_path
    return False, None

def handle_convert(args):
    """
    Handles comic conversion and returns a list of newly created/processed file paths.
    """
    print_header_line("Comic Conversion", color=Style.GREEN)
    
    files_to_process_map = {}
    for path_arg in args.paths:
        abs_path = os.path.abspath(os.path.expanduser(path_arg))
        if os.path.exists(abs_path):
            output_dir = os.path.join(os.path.dirname(abs_path) if os.path.isfile(abs_path) else abs_path, "converted")
            if output_dir not in files_to_process_map:
                files_to_process_map[output_dir] = []
            files_to_process_map[output_dir].append(abs_path)

    if not files_to_process_map:
        print_info("No valid files or directories found for conversion.")
        return []

    successful_new_paths = []
    for output_dir, file_paths in files_to_process_map.items():
        os.makedirs(output_dir, exist_ok=True)
        print_info(f"\nProcessing files. Outputting to: {output_dir}")
        
        for file_path in sorted(list(set(file_paths))):
            if os.path.abspath(os.path.dirname(file_path)) == os.path.abspath(output_dir):
                continue

            print(f"\n{Style.BOLD}{Style.YELLOW}--- Converting: {os.path.basename(file_path)} ---{Style.RESET}")
            ext = os.path.splitext(file_path)[1].lower()
            success, new_path = False, None
            
            if ext == ".cbr": success, new_path = convert_cbr_to_cbz(file_path, output_dir)
            elif ext == ".cb7": success, new_path = convert_cb7_to_cbz(file_path, output_dir)
            elif ext == ".cbt": success, new_path = convert_cbt_to_cbz(file_path, output_dir)
            elif ext == ".pdf": success, new_path = convert_pdf_to_cbz(file_path, output_dir)
            elif ext == ".cbz":
                # If a CBZ is a source, we just "process" it by ensuring it's in our successful list.
                # If it's already in the destination, we use that path.
                target_cbz_path = os.path.join(output_dir, os.path.basename(file_path))
                if not os.path.exists(target_cbz_path):
                    try:
                        shutil.copy2(file_path, target_cbz_path)
                        print_success(f"  Copied existing CBZ to: {os.path.basename(target_cbz_path)}")
                    except Exception as e:
                        print_error(f"  Failed to copy CBZ: {e}")
                else:
                    print_info(f"  CBZ already exists in target directory.")
                success, new_path = True, target_cbz_path # It is now successfully "processed"
            
            if success and new_path:
                successful_new_paths.append(new_path)

    print_header_line("Conversion Summary", color=Style.GREEN)
    print_info(f"  Successfully processed/converted {len(successful_new_paths)} file(s).")
    return successful_new_paths