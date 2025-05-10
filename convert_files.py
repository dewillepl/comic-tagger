#!/usr/bin/env python3

import os
import shutil
import subprocess
import zipfile
import tarfile
import tempfile
import natsort # For natural sorting of image filenames within CBZ

# Import utilities
from utils import (
    Style, print_error, print_info, print_success,
    print_header_line
)

# --- Conversion Helper Functions ---

def check_command_exists(command):
    """Checks if a command-line tool is available in the system's PATH."""
    return shutil.which(command) is not None

def natural_sort_key_for_convert(s, _nsre=natsort.natsort_keygen()):
    """Key for natural sorting of image filenames, specific to conversion module."""
    return _nsre(s)

def create_cbz_from_images(image_folder, cbz_output_path):
    """
    Creates a CBZ file from a folder of images.
    Images are sorted naturally before being added to the archive.
    """
    # This print_info is for the specific action, not a general script info message
    print(f"  {Style.CYAN}Creating CBZ:{Style.RESET} {os.path.basename(cbz_output_path)}")
    try:
        # List and sort image files (common image extensions)
        images = sorted(
            [os.path.join(image_folder, f) for f in os.listdir(image_folder)
             if os.path.isfile(os.path.join(image_folder, f)) and
             f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.jxl'))], # Added jxl
            key=natural_sort_key_for_convert
        )

        if not images:
            print_error(f"    No compatible image files found in {image_folder} to create CBZ.")
            return False

        with zipfile.ZipFile(cbz_output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, image_path in enumerate(images):
                _, ext = os.path.splitext(image_path)
                # Consistent naming scheme within the CBZ for pages
                archive_image_name = f"page_{i+1:04d}{ext}" # e.g., page_0001.jpg
                zf.write(image_path, arcname=archive_image_name)
                # Verbose logging of each added image can be too much for large archives.
                # print_info(f"    Added to CBZ: {os.path.basename(image_path)} as {archive_image_name}")
        print_success(f"  Successfully created {os.path.basename(cbz_output_path)}")
        return True
    except Exception as e:
        print_error(f"    Failed to create CBZ {os.path.basename(cbz_output_path)}: {e}")
        return False

# At the top of convert_files.py, make sure zipfile is imported (it should be already)
# import zipfile # Already there for create_cbz_from_images

def _extract_zip_for_cbr_fallback(archive_path, temp_extract_dir):
    """Helper to attempt ZIP extraction for a misnamed CBR."""
    print(f"    {Style.BRIGHT_BLACK}unrar failed (not RAR archive). Attempting to extract as ZIP...{Style.RESET}")
    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            # Filter members to extract only image files
            image_members = [
                memberinfo for memberinfo in zf.infolist() 
                if not memberinfo.is_dir() and \
                os.path.splitext(memberinfo.filename)[1].lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.jxl')
            ]
            if not image_members:
                print_error(f"    No compatible image files found within {os.path.basename(archive_path)} when treated as ZIP.")
                return False
            
            zf.extractall(path=temp_extract_dir, members=image_members)
        # print_info(f"    Successfully extracted as ZIP.") # Implied by create_cbz success
        return True
    except zipfile.BadZipFile:
        print_error(f"    File {os.path.basename(archive_path)} is also not a valid ZIP archive.")
        return False
    except Exception as e:
        print_error(f"    Error extracting {os.path.basename(archive_path)} as ZIP: {e}")
        return False


def convert_cbr_to_cbz(cbr_path, output_dir):
    """Converts a CBR (RAR or misnamed ZIP) file to CBZ."""
    # unrar is still the primary tool for .cbr
    unrar_available = check_command_exists("unrar")
    
    base_name = os.path.splitext(os.path.basename(cbr_path))[0]
    cbz_output_path = os.path.join(output_dir, f"{base_name}.cbz")

    if os.path.exists(cbz_output_path):
        print_info(f"  Skipping CBR conversion, CBZ already exists: {os.path.basename(cbz_output_path)}")
        return True
        
    print(f"  {Style.CYAN}Converting CBR-like file:{Style.RESET} {os.path.basename(cbr_path)} -> {os.path.basename(cbz_output_path)}")

    with tempfile.TemporaryDirectory(prefix="cbr_extract_") as temp_extract_dir:
        extraction_method_successful = False
        
        if unrar_available:
            print(f"    {Style.BRIGHT_BLACK}Attempting extraction with unrar...{Style.RESET}")
            cmd = ["unrar", "e", "-o+", "-y", cbr_path, temp_extract_dir + os.sep]
            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='ignore')
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    extraction_method_successful = True
                elif "is not RAR archive" in stderr or "is not RAR archive" in stdout : # Check both stdout/stderr
                    # Not a RAR archive, try ZIP fallback
                    if _extract_zip_for_cbr_fallback(cbr_path, temp_extract_dir):
                        extraction_method_successful = True
                    else:
                        # _extract_zip_for_cbr_fallback already printed errors
                        return False # Failed both unrar and zip
                else: # unrar failed for other reasons
                    print_error(f"    unrar execution failed for {os.path.basename(cbr_path)} (return code: {process.returncode}).")
                    if stderr and stderr.strip():
                        print_error(f"    RAR Error Output:\n{Style.BRIGHT_BLACK}{stderr.strip()}{Style.RESET}")
                    elif stdout and stdout.strip():
                        print_error(f"    RAR Standard Output (may contain error info):\n{Style.BRIGHT_BLACK}{stdout.strip()}{Style.RESET}")
                    return False # unrar failed definitively
            except FileNotFoundError:
                print_error("`unrar` command somehow not found during execution (should be caught by check).")
                return False # Should not happen if unrar_available was true
            except Exception as e:
                print_error(f"    An unexpected error occurred during unrar attempt: {e}")
                # Fall through to try ZIP if unrar itself had an execution error (not just content error)
                # Or decide to return False here. For now, let's try ZIP if unrar call itself failed.
                if _extract_zip_for_cbr_fallback(cbr_path, temp_extract_dir):
                    extraction_method_successful = True
                else:
                    return False
        else: # unrar is not available, try ZIP directly for .cbr files
            print_info("  `unrar` command not found. Attempting to treat .cbr as .zip as a fallback.")
            if _extract_zip_for_cbr_fallback(cbr_path, temp_extract_dir):
                extraction_method_successful = True
            else:
                return False # Failed zip and no unrar

        # After attempting extraction (either unrar or zip fallback)
        if extraction_method_successful:
            # print_info(f"    Extraction successful.") # Implied by create_cbz success
            return create_cbz_from_images(temp_extract_dir, cbz_output_path)
        else:
            # If we reach here, all attempts failed or one failed without a fallback.
            # Error messages should have been printed by the failing methods.
            print_error(f"    Could not extract images from {os.path.basename(cbr_path)} using available methods.")
            return False

def convert_cb7_to_cbz(cb7_path, output_dir):
    """Converts a CB7 (7-Zip) file to CBZ using the '7z' command."""
    if not check_command_exists("7z"):
        print_error("`7z` command not found. Please install p7zip to convert CB7 files.")
        return False

    base_name = os.path.splitext(os.path.basename(cb7_path))[0]
    cbz_output_path = os.path.join(output_dir, f"{base_name}.cbz")

    if os.path.exists(cbz_output_path):
        print_info(f"  Skipping CB7 conversion, CBZ already exists: {os.path.basename(cbz_output_path)}")
        return True
        
    print_info(f"  Converting CB7: {os.path.basename(cb7_path)} -> {os.path.basename(cbz_output_path)}")

    with tempfile.TemporaryDirectory(prefix="cb7_extract_") as temp_extract_dir:
        # print_info(f"  Extracting {os.path.basename(cb7_path)} to {temp_extract_dir}...")
        # 7z x <archive> -o<path_to_extract> -y (extract with full paths, specify output, assume yes)
        cmd = ["7z", "x", cb7_path, f"-o{temp_extract_dir}", "-y"]
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                print_error(f"    7z failed for {os.path.basename(cb7_path)}.")
                error_output = stderr.decode(errors='ignore').strip()
                if error_output: print_error(f"    7z Error: {error_output}")
                return False
            # print_info(f"    Extraction successful.")
            return create_cbz_from_images(temp_extract_dir, cbz_output_path)
        except Exception as e:
            print_error(f"    Error during CB7 conversion process: {e}")
            return False

def convert_cbt_to_cbz(cbt_path, output_dir):
    """Converts a CBT (TAR archive) file to CBZ using Python's tarfile module."""
    base_name = os.path.splitext(os.path.basename(cbt_path))[0]
    cbz_output_path = os.path.join(output_dir, f"{base_name}.cbz")

    if os.path.exists(cbz_output_path):
        print_info(f"  Skipping CBT conversion, CBZ already exists: {os.path.basename(cbz_output_path)}")
        return True

    print_info(f"  Converting CBT: {os.path.basename(cbt_path)} -> {os.path.basename(cbz_output_path)}")

    with tempfile.TemporaryDirectory(prefix="cbt_extract_") as temp_extract_dir:
        # print_info(f"  Extracting {os.path.basename(cbt_path)} to {temp_extract_dir}...")
        try:
            with tarfile.open(cbt_path, 'r:*') as tar: # r:* attempts to auto-detect compression
                # Filter members to extract only image files and avoid issues like path traversal
                # (though tarfile.extractall to a specific path is generally safe)
                members_to_extract = []
                for member in tar.getmembers():
                    if member.isfile() and member.name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.jxl')):
                        members_to_extract.append(member)
                    elif member.isfile(): # Log skipped non-image files if any
                        print_info(f"    Skipping non-image file in CBT: {member.name}")
                
                if not members_to_extract:
                    print_error(f"    No compatible image files found in CBT: {os.path.basename(cbt_path)}")
                    return False

                tar.extractall(path=temp_extract_dir, members=members_to_extract)
            # print_info(f"    Extraction successful.")
            return create_cbz_from_images(temp_extract_dir, cbz_output_path)
        except tarfile.ReadError as e: # Specific error for TAR files
            print_error(f"    Failed to read CBT file {os.path.basename(cbt_path)} (possibly corrupted or unsupported format): {e}")
            return False
        except Exception as e:
            print_error(f"    Error during CBT conversion process: {e}")
            return False

def convert_pdf_to_cbz(pdf_path, output_dir):
    """Converts a PDF file to CBZ using the 'mutool' command."""
    if not check_command_exists("mutool"):
        print_error("`mutool` command not found. Please install MuPDF tools to convert PDF files.")
        return False

    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    cbz_output_path = os.path.join(output_dir, f"{base_name}.cbz")

    if os.path.exists(cbz_output_path):
        print_info(f"  Skipping PDF conversion, CBZ already exists: {os.path.basename(cbz_output_path)}")
        return True
        
    print_info(f"  Converting PDF: {os.path.basename(pdf_path)} -> {os.path.basename(cbz_output_path)}")

    with tempfile.TemporaryDirectory(prefix="pdf_extract_") as temp_extract_dir:
        # print_info(f"  Extracting images from {os.path.basename(pdf_path)} to {temp_extract_dir}...")
        # mutool draw -o <output_folder/page-%04d.png> -r <dpi> <input.pdf>
        output_pattern = os.path.join(temp_extract_dir, "page-%04d.png") # e.g., page-0001.png
        cmd = ["mutool", "draw", "-o", output_pattern, "-r", "150", pdf_path] # Use 150 DPI as a default
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate() # Wait for completion
            
            # Check if any PNG images were actually created by mutool
            if not any(f.lower().endswith(".png") for f in os.listdir(temp_extract_dir)):
                # If no images, then check return code and stderr for more info
                if process.returncode != 0: # mutool might return non-zero for warnings too
                    print_error(f"    mutool failed for {os.path.basename(pdf_path)} (return code: {process.returncode}).")
                    error_output = stderr.decode(errors='ignore').strip()
                    if error_output: print_error(f"    MuPDF Error: {error_output}")
                else: # Successful return code but no images
                    print_error(f"    mutool ran for {os.path.basename(pdf_path)} but no images were extracted.")
                return False

            # print_info(f"    Image extraction successful.")
            return create_cbz_from_images(temp_extract_dir, cbz_output_path)
        except Exception as e:
            print_error(f"    Error during PDF conversion process: {e}")
            return False

# --- Main Handler for 'convert' command ---
def handle_convert(args):
    """
    Handles comic conversion operations based on parsed arguments.
    This is the function called by comic_tagger_cli.py for the 'convert' command.
    """
    print_header_line("Comic Conversion", color=Style.GREEN)
    
    # Map: {output_directory_for_converted_files: [list_of_input_file_paths_for_this_output_dir]}
    files_to_process_map = {} 

    for path_arg in args.paths: # args.paths comes from argparse (nargs='+')
        abs_path_arg = os.path.abspath(os.path.expanduser(path_arg))

        if not os.path.exists(abs_path_arg):
            print_error(f"Input path not found: {abs_path_arg}")
            continue

        current_converted_output_dir = None
        files_for_current_batch = []

        if os.path.isfile(abs_path_arg):
            input_file_dir = os.path.dirname(abs_path_arg)
            current_converted_output_dir = os.path.join(input_file_dir, "converted")
            
            # Avoid processing a file if it's already inside ITS OWN 'converted' directory
            if os.path.basename(input_file_dir).lower() == "converted":
                # Check if the parent of 'converted' exists and if the file also exists there (original location)
                # This is a heuristic to avoid re-processing from an output folder if it's somehow given as input.
                # For single file input, this mostly means if user points to /path/converted/file.cbr, we might skip.
                print_info(f"  Note: Input file {os.path.basename(abs_path_arg)} is in a 'converted' directory. Processing if not already target.")

            files_for_current_batch.append(abs_path_arg)

        elif os.path.isdir(abs_path_arg):
            input_dir_path = abs_path_arg
            current_converted_output_dir = os.path.join(input_dir_path, "converted")
            
            # print_info(f"Scanning top-level of directory: {input_dir_path}")
            for item_name in os.listdir(input_dir_path):
                item_path = os.path.join(input_dir_path, item_name)
                # Process only files directly in this directory (not recursive for subdirs)
                if os.path.isfile(item_path):
                    # Ensure we don't pick up files from the target 'converted' dir itself
                    if os.path.commonpath([os.path.dirname(item_path), current_converted_output_dir]) == current_converted_output_dir and \
                       os.path.basename(os.path.dirname(item_path)).lower() == "converted":
                        continue # This file is inside the 'converted' dir of the input_dir_path
                    files_for_current_batch.append(item_path)
        
        if current_converted_output_dir and files_for_current_batch:
            if current_converted_output_dir not in files_to_process_map:
                files_to_process_map[current_converted_output_dir] = []
            files_to_process_map[current_converted_output_dir].extend(files_for_current_batch)

    if not files_to_process_map:
        print_info("No valid files or directories found to process for conversion based on input.")
        return

    # Overall summary counters
    total_converted_successfully = 0
    total_failed_to_convert = 0
    total_skipped_as_cbz = 0
    total_skipped_unsupported = 0

    for converted_output_dir, files_in_batch in files_to_process_map.items():
        if not files_in_batch:
            continue

        os.makedirs(converted_output_dir, exist_ok=True)
        print_info(f"\nProcessing files. Outputting to: {converted_output_dir}")
        
        # Deduplicate and sort files for this specific output directory batch
        unique_files_for_this_batch = sorted(list(set(files_in_batch)))

        for file_path in unique_files_for_this_batch:
            # Final check: if the file is ALREADY in the target 'converted' dir, skip.
            # This mostly applies if a file was listed explicitly that happens to be there.
            if os.path.abspath(os.path.dirname(file_path)) == os.path.abspath(converted_output_dir):
                # e.g. input /path/to/converted/file.pdf, output dir is /path/to/converted
                # This means we are trying to convert a file from the target output dir back into itself.
                # We should only process source files. The convert_xxx_to_cbz functions also have
                # a check `if os.path.exists(cbz_output_path)` which handles this for the target CBZ.
                 if os.path.splitext(file_path)[1].lower() != ".cbz": # Don't re-convert non-cbz in output dir
                    print_info(f"  Skipping conversion for {os.path.basename(file_path)} as it's already in the target output directory.")
                    continue


            print(f"\n{Style.BOLD}{Style.YELLOW}--- Converting: {os.path.basename(file_path)} ---{Style.RESET}")
            print_info(f"  Source: {file_path}")

            ext = os.path.splitext(file_path)[1].lower()
            conversion_succeeded = False
            
            if ext == ".cbr": conversion_succeeded = convert_cbr_to_cbz(file_path, converted_output_dir)
            elif ext == ".cb7": conversion_succeeded = convert_cb7_to_cbz(file_path, converted_output_dir)
            elif ext == ".cbt": conversion_succeeded = convert_cbt_to_cbz(file_path, converted_output_dir)
            elif ext == ".pdf": conversion_succeeded = convert_pdf_to_cbz(file_path, converted_output_dir)
            elif ext == ".cbz":
                # If a CBZ is a source and it's not already in the target 'converted' folder, copy it.
                target_cbz_path = os.path.join(converted_output_dir, os.path.basename(file_path))
                if os.path.abspath(file_path) != os.path.abspath(target_cbz_path):
                    try:
                        shutil.copy2(file_path, target_cbz_path)
                        print_success(f"  Copied existing CBZ to: {os.path.basename(target_cbz_path)}")
                        conversion_succeeded = True 
                    except Exception as e:
                        print_error(f"  Failed to copy existing CBZ {os.path.basename(file_path)}: {e}")
                        conversion_succeeded = False
                else: # Already in target location or is the target
                    print_info(f"  CBZ file {os.path.basename(file_path)} is already in the target output directory or is the source itself.")
                    # This case might count as "skipped" if no copy action.
                    # If copy happened, it's a success.
                total_skipped_as_cbz += 1 # Increment regardless of copy for "skipped as CBZ" count
            else:
                total_skipped_unsupported += 1
                print_info(f"  Skipping unsupported file type: {ext}")
                continue # Go to next file in batch
            
            if conversion_succeeded:
                total_converted_successfully += 1
            else:
                # Error message should have been printed by the specific convert_xxx function
                total_failed_to_convert +=1
    
    # Print Overall Summary
    print_header_line("Overall Conversion Summary", color=Style.GREEN)
    print_info(f"  Successfully converted/processed: {Style.GREEN}{total_converted_successfully}{Style.RESET} file(s)")
    if total_failed_to_convert > 0:
        print_info(f"  Failed to convert:              {Style.RED}{total_failed_to_convert}{Style.RESET} file(s)")
    # Adjust skipped_as_cbz count: if a CBZ was successfully copied, it's in total_converted_successfully.
    # We only want to report CBZs that were truly skipped without action.
    actual_skipped_cbz_no_action = total_skipped_as_cbz - (total_converted_successfully if any(p.lower().endswith(".cbz") for batch in files_to_process_map.values() for p in batch) else 0)

    if total_skipped_as_cbz > 0: # If any CBZ was encountered as input
        print_info(f"  CBZs encountered as input:      {Style.BRIGHT_BLACK}{total_skipped_as_cbz}{Style.RESET} file(s)")
    if total_skipped_unsupported > 0:
        print_info(f"  Skipped (unsupported type):     {Style.BRIGHT_BLACK}{total_skipped_unsupported}{Style.RESET} file(s)")