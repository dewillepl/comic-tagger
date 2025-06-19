#!/usr/bin/env python3

import argparse
import sys
import os
import glob
from types import SimpleNamespace

from fetch_api import handle_fetch_comicvine, display_volume_details
from tagging import handle_tagging_dispatch
from convert_files import handle_convert
from inspect_files import handle_check
from utils import Style, print_header_line, print_info, print_error, print_success

class ApplicationState:
    """Stores the application state, primarily the list of loaded files."""
    def __init__(self, paths):
        self.loaded_files = self.expand_paths(paths)

    def expand_paths(self, paths):
        file_list = set()
        supported_extensions = ('.cbz', '.cbr', '.cb7', '.cbt', '.pdf')
        for path_arg in paths:
            user_path = os.path.expanduser(path_arg)
            paths_to_check = [user_path] if os.path.exists(user_path) else glob.glob(user_path)
            if not paths_to_check:
                print_error(f"Path or pattern not found: {path_arg}"); continue
            for path in paths_to_check:
                if os.path.isfile(path) and path.lower().endswith(supported_extensions):
                    file_list.add(os.path.abspath(path))
                elif os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for name in files:
                            if name.lower().endswith(supported_extensions):
                                file_list.add(os.path.abspath(os.path.join(root, name)))
        return sorted(list(file_list))

    def update_filepath(self, old_path, new_path):
        abs_old, abs_new = os.path.abspath(old_path), os.path.abspath(new_path)
        if abs_old in self.loaded_files:
            self.loaded_files.remove(abs_old)
            self.loaded_files.append(abs_new)
            self.loaded_files.sort()

    def update_after_conversion(self, newly_created_files):
        current_cbz = {f for f in self.loaded_files if f.lower().endswith('.cbz')}
        new_cbz = set(os.path.abspath(f) for f in newly_created_files)
        self.loaded_files = sorted(list(current_cbz.union(new_cbz)))
        print_success("Application state automatically updated.")


def get_user_input(prompt, required=False):
    while True:
        value = input(f"{Style.YELLOW}{prompt}{Style.RESET}").strip()
        if value or not required: return value
        print_error("This field is required.")

def select_file_from_list(files, prompt="Select a file"):
    if not files:
        print_error("No files loaded to select from."); return None
    if len(files) == 1: return files[0]
    print_header_line("Select File", color=Style.CYAN)
    for i, file_path in enumerate(files, 1): print(f"  {i}. {os.path.basename(file_path)}")
    print("-" * 40)
    while True:
        try:
            choice = get_user_input(f"{prompt} (1-{len(files)}): ", required=True)
            index = int(choice) - 1
            if 0 <= index < len(files): return files[index]
            else: print_error("Invalid selection.")
        except ValueError: print_error("Please enter a valid number.")

def run_search_to_tag_wizard(state):
    """A step-by-step workflow from searching to tagging."""
    print_header_line("Step 1: Search for a Volume", color=Style.GREEN)
    title = get_user_input("Enter Title (optional): ")
    author = get_user_input("Enter Author (optional): ")
    publisher = get_user_input("Enter Publisher (optional): ")
    year = get_user_input("Enter Start Year (optional): ")

    if not any([title, author, publisher, year]):
        print_error("At least one search criterion is required."); return

    args = SimpleNamespace(cv_name_filter=title or None, cv_author_name=author or None, cv_publisher_name=publisher or None, cv_start_year=int(year) if year.isdigit() else None)
    volume_results = handle_fetch_comicvine(args)
    if not volume_results: return

    while True:
        prompt = f"\nEnter Result # (1-{len(volume_results)}) to see details, or 'b' to go back to Main Menu: "
        vol_choice = get_user_input(prompt, required=True)
        if vol_choice.lower() == 'b': return

        try:
            index = int(vol_choice) - 1
            if not (0 <= index < len(volume_results)): print_error("Invalid selection."); continue
        except ValueError: print_error("Invalid input."); continue
        
        selected_volume = volume_results[index]
        volume_details = handle_fetch_comicvine(SimpleNamespace(get_volume=selected_volume.get('id')))
        if not (volume_details and volume_details.get('issues')):
            print_error("This volume has no issues listed or failed to load details."); continue

        issue_map = {str(issue.get('issue_number')): issue.get('id') for issue in volume_details['issues']}
        while True:
            issue_choice = get_user_input("Enter Issue # to see details, or 'b' to go back to Main Menu: ", required=True)
            if issue_choice.lower() == 'b': return

            issue_id = issue_map.get(issue_choice)
            if not issue_id:
                print_error(f"Issue #{issue_choice} not found."); continue

            translate_desc = 'pl' if get_user_input("Translate description? (y/n): ").lower() == 'y' else None
            handle_fetch_comicvine(SimpleNamespace(get_issue=issue_id, translate_description=translate_desc, verbose=True))

            print("\n" + "-"*40)
            print(f" 1. Tag a file with this issue (ID: {issue_id})")
            print(" 2. Back to issue selection")
            tag_choice = get_user_input("Choose an option: ")

            if tag_choice == '1':
                cbz_files = [f for f in state.loaded_files if f.lower().endswith('.cbz')]
                if not cbz_files:
                    print_error("No .cbz files loaded to tag."); continue
                target_file = select_file_from_list(cbz_files, "Select a .cbz file to tag")
                if not target_file: continue

                rename = get_user_input("Rename file after tagging? (y/n): ").lower() == 'y'
                overwrite = get_user_input("Overwrite all existing tags? (y/n): ").lower() == 'y'
                tag_args = SimpleNamespace(issue_id=issue_id, cbz_file_path=target_file, rename=rename, translate=translate_desc, overwrite_all=overwrite)
                
                success, new_path = handle_tagging_dispatch(tag_args)
                if success and new_path != target_file: state.update_filepath(target_file, new_path)
                
                print_info("Tagging process finished. Returning to issue selection...")
                display_volume_details(volume_details)
            elif tag_choice == '2':
                display_volume_details(volume_details)

def show_tag_manager_menu(state):
    """Handles local file tagging operations like checking and erasing."""
    while True:
        cbz_files = [f for f in state.loaded_files if f.lower().endswith('.cbz')]
        if not cbz_files:
            print_error("No .cbz files loaded to manage."); input("Press Enter..."); return
        target_file = select_file_from_list(cbz_files, "Select a .cbz file to manage")
        if not target_file: return
        while True:
            print_header_line(f"Tag Manager: {os.path.basename(target_file)}", color=Style.GREEN)
            print(" 1. Check existing tags\n 2. Erase tags\n 3. Select another file\n 4. Back to Main Menu")
            choice = get_user_input("Choose an option: ")
            if choice == '1':
                if os.path.exists(target_file): handle_check(SimpleNamespace(paths=[target_file]))
                else: print_error(f"File '{os.path.basename(target_file)}' no longer exists.")
                input("\nPress Enter...")
            elif choice == '2':
                if os.path.exists(target_file) and get_user_input(f"Erase tags from {os.path.basename(target_file)}? (y/n): ").lower() == 'y':
                    handle_tagging_dispatch(SimpleNamespace(erase=True, cbz_file_path=target_file))
            elif choice == '3': break
            elif choice == '4': return
            else: print_error("Invalid option.")

def show_convert_menu(state):
    """Convert menu logic with automatic state update."""
    files_to_convert = [f for f in state.loaded_files if not f.lower().endswith('.cbz')]
    print_header_line("Convert Menu", color=Style.GREEN)
    if not files_to_convert:
        print_info("No files loaded that require conversion."); input("\nPress Enter..."); return
    print("The following files can be converted to .cbz:")
    for f in files_to_convert: print(f"  - {os.path.basename(f)}")
    print("\n 1. Convert all applicable files\n 2. Back to Main Menu")
    choice = get_user_input("Choose an option: ")
    if choice == '1':
        newly_created_files = handle_convert(SimpleNamespace(paths=files_to_convert))
        if newly_created_files: state.update_after_conversion(newly_created_files)
        else: print_info("No new files were created.")
        input("\nPress Enter...")

def main():
    """Main application function."""
    parser = argparse.ArgumentParser(description="Interactive Comic Tagger.")
    parser.add_argument('paths', nargs='+', help="Path(s) to comic file(s) or directory(ies).")
    try:
        import natsort
    except ImportError:
        print(f"{Style.RED}Fatal Error: 'natsort' is required.{Style.RESET} (pip install natsort)"); sys.exit(1)
    
    state = ApplicationState(parser.parse_args().paths)
    if not state.loaded_files:
        print_error("No supported comic files found. Exiting."); sys.exit(1)

    while True:
        print_header_line("Main Menu", color=Style.MAGENTA)
        print(f"Loaded {len(state.loaded_files)} file(s).")
        print("\n 1. Search & Tag Workflow\n 2. Tag Manager (Local Files)\n 3. Convert Files to CBZ\n 4. List Loaded Files\n 5. Exit")
        choice = get_user_input("Choose an option: ")
        if choice == '1': run_search_to_tag_wizard(state)
        elif choice == '2': show_tag_manager_menu(state)
        elif choice == '3': show_convert_menu(state)
        elif choice == '4':
            print_header_line("Loaded Files", color=Style.CYAN)
            if state.loaded_files:
                for f in state.loaded_files: print(f"  - {f}")
            else: print_info("No files are currently loaded.")
            input("\nPress Enter...")
        elif choice == '5':
            print_info("Exiting. Goodbye!"); sys.exit(0)
        else: print_error("Invalid option.")

if __name__ == "__main__":
    main()