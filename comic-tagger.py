#!/usr/bin/env python3

import argparse
import sys
import os
import glob
from types import SimpleNamespace

from fetch_api import handle_fetch_comicvine
from tagging import handle_tagging_dispatch
from convert_files import handle_convert
from inspect_files import handle_check
from utils import Style, print_header_line, print_info, print_error, print_success

class ApplicationState:
    """Stores the application state, primarily the list of loaded files."""
    def __init__(self, paths):
        self.original_paths = paths
        self.loaded_files = self.expand_paths(paths)

    def expand_paths(self, paths):
        file_list = set()
        supported_extensions = ('.cbz', '.cbr', '.cb7', '.cbt', '.pdf')
        for path_arg in paths:
            user_path = os.path.expanduser(path_arg)
            paths_to_check = [user_path] if os.path.exists(user_path) else glob.glob(user_path)
            if not paths_to_check:
                print_error(f"Path or pattern not found: {path_arg}")
                continue
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
        """Updates a single filepath in the state, e.g., after a rename."""
        abs_old, abs_new = os.path.abspath(old_path), os.path.abspath(new_path)
        if abs_old in self.loaded_files:
            self.loaded_files.remove(abs_old)
            self.loaded_files.append(abs_new)
            self.loaded_files.sort()
            print_info(f"Application state updated: '{os.path.basename(old_path)}' -> '{os.path.basename(new_path)}'")

    def update_after_conversion(self, newly_created_files):
        """Rebuilds the file list to only include CBZ files after conversion."""
        current_cbz = {f for f in self.loaded_files if f.lower().endswith('.cbz')}
        new_cbz = set(os.path.abspath(f) for f in newly_created_files)
        self.loaded_files = sorted(list(current_cbz.union(new_cbz)))
        print_success("Application state automatically updated with converted files.")


def get_user_input(prompt, required=False):
    """Helper to get non-empty input from the user."""
    while True:
        value = input(f"{Style.YELLOW}{prompt}{Style.RESET}").strip()
        if value or not required: return value
        print_error("This field is required.")

def select_file_from_list(files, prompt="Select a file"):
    """Lets the user select a file from a list."""
    if not files:
        print_error("No files loaded to select from.")
        return None
    if len(files) == 1:
        return files[0]

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

def show_search_and_tag_menu(state):
    """Handles searching ComicVine and tagging files directly."""
    while True:
        print_header_line("Search & Tag from ComicVine", color=Style.GREEN)
        print(" 1. Search for Volume")
        print(" 2. Get Volume Details (by ID)")
        print(" 3. Get Issue Details (by ID)")
        print(" 4. Tag from ComicVine Issue ID")
        print(" 5. Back to Main Menu")
        choice = get_user_input("Choose an option: ")

        if choice == '1':
            title = get_user_input("Enter Title (optional): ")
            author = get_user_input("Enter Author (optional): ")
            year = get_user_input("Enter Start Year (optional): ")
            publisher = get_user_input("Enter Publisher (optional): ")
            args = SimpleNamespace(cv_name_filter=title or None, cv_author_name=author or None, cv_start_year=int(year) if year.isdigit() else None, cv_publisher_name=publisher or None, get_issue=None, get_volume=None)
            handle_fetch_comicvine(args)
        elif choice == '2':
            volume_id = get_user_input("Enter Volume ID: ", required=True)
            if volume_id.isdigit(): handle_fetch_comicvine(SimpleNamespace(get_volume=int(volume_id), get_issue=None))
        elif choice == '3':
            issue_id = get_user_input("Enter Issue ID: ", required=True)
            if issue_id.isdigit():
                translate_title = 'pl' if get_user_input("Translate Title? (y/n): ").lower() == 'y' else None
                translate_desc = 'pl' if get_user_input("Translate Description? (y/n): ").lower() == 'y' else None
                verbose = get_user_input("Show verbose details? (y/n): ").lower() == 'y'
                args = SimpleNamespace(get_issue=int(issue_id), translate_title=translate_title, translate_description=translate_desc, verbose=verbose, get_volume=None)
                handle_fetch_comicvine(args)
        elif choice == '4':
            cbz_files = [f for f in state.loaded_files if f.lower().endswith('.cbz')]
            if not cbz_files:
                print_error("No .cbz files loaded to tag.")
                input("Press Enter to continue...")
                continue
            
            target_file = select_file_from_list(cbz_files, "Select a .cbz file to tag")
            if not target_file: continue

            issue_id = get_user_input("Enter ComicVine Issue ID to tag with: ", required=True)
            if not issue_id.isdigit(): continue

            rename = get_user_input("Rename file after tagging? (y/n): ").lower() == 'y'
            translate = 'pl' if get_user_input("Translate description? (y/n): ").lower() == 'y' else None
            overwrite = get_user_input("Overwrite all existing tags? (y/n): ").lower() == 'y'

            args = SimpleNamespace(issue_id=int(issue_id), cbz_file_path=target_file, rename=rename, translate=translate, overwrite_all=overwrite)
            success, new_path = handle_tagging_dispatch(args)
            if success and new_path != target_file:
                state.update_filepath(target_file, new_path)
            input("\nPress Enter to continue...")
        elif choice == '5': break
        else: print_error("Invalid option.")

def show_tag_manager_menu(state):
    """Handles local file tagging operations like checking and erasing."""
    while True:
        cbz_files = [f for f in state.loaded_files if f.lower().endswith('.cbz')]
        if not cbz_files:
            print_error("No .cbz files loaded to manage.")
            input("Press Enter to continue...")
            return

        target_file = select_file_from_list(cbz_files, "Select a .cbz file to manage")
        if not target_file: return

        while True:
            print_header_line(f"Tag Manager: {os.path.basename(target_file)}", color=Style.GREEN)
            print(" 1. Check existing tags")
            print(" 2. Erase tags")
            print(" 3. Select another file")
            print(" 4. Back to Main Menu")
            choice = get_user_input("Choose an option: ")

            if choice == '1':
                if os.path.exists(target_file):
                    handle_check(SimpleNamespace(paths=[target_file]))
                else: print_error(f"File '{os.path.basename(target_file)}' no longer exists.")
                input("\nPress Enter to continue...")
            elif choice == '2':
                if os.path.exists(target_file):
                    if get_user_input(f"Erase all tags from {os.path.basename(target_file)}? (y/n): ").lower() == 'y':
                        handle_tagging_dispatch(SimpleNamespace(erase=True, cbz_file_path=target_file))
                else: print_error(f"File '{os.path.basename(target_file)}' no longer exists.")
            elif choice == '3': break
            elif choice == '4': return
            else: print_error("Invalid option.")

def show_convert_menu(state):
    """Convert menu logic with automatic state update."""
    files_to_convert = [f for f in state.loaded_files if not f.lower().endswith('.cbz')]
    print_header_line("Convert Menu", color=Style.GREEN)
    
    if not files_to_convert:
        print_info("No files loaded that require conversion.")
        input("\nPress Enter to return to the Main Menu...")
        return

    print("The following files can be converted to .cbz:")
    for f in files_to_convert: print(f"  - {os.path.basename(f)}")
    print("\n 1. Convert all applicable files")
    print(" 2. Back to Main Menu")
    
    choice = get_user_input("Choose an option: ")

    if choice == '1':
        newly_created_files = handle_convert(SimpleNamespace(paths=files_to_convert))
        if newly_created_files:
            state.update_after_conversion(newly_created_files)
        else:
            print_info("No new files were created during conversion.")
        input("\nPress Enter to return to the Main Menu...")

def main():
    """Main application function."""
    parser = argparse.ArgumentParser(description="Interactive Comic Tagger.")
    parser.add_argument('paths', nargs='+', help="Path(s) to comic file(s) or directory(ies).")
    
    try:
        import natsort
    except ImportError:
        print(f"{Style.RED}Fatal Error: 'natsort' is required.{Style.RESET} (pip install natsort)")
        sys.exit(1)

    parsed_args = parser.parse_args()
    state = ApplicationState(parsed_args.paths)
    
    if not state.loaded_files:
        print_error("No supported comic files found in the specified paths. Exiting.")
        sys.exit(1)

    while True:
        print_header_line("Main Menu", color=Style.MAGENTA)
        print(f"Loaded {len(state.loaded_files)} file(s).")
        print("\n" + "-"*20)
        print(" 1. Search & Tag from ComicVine")
        print(" 2. Tag Manager")
        print(" 3. Convert Files to CBZ")
        print(" 4. List Loaded Files")
        print(" 5. Exit")
        print("-"*20)

        choice = get_user_input("Choose an option: ")

        if choice == '1': show_search_and_tag_menu(state)
        elif choice == '2': show_tag_manager_menu(state)
        elif choice == '3': show_convert_menu(state)
        elif choice == '4':
            print_header_line("Loaded Files", color=Style.CYAN)
            if state.loaded_files:
                for f in state.loaded_files: print(f"  - {f}")
            else: print_info("No files are currently loaded.")
            input("\nPress Enter to continue...")
        elif choice == '5':
            print_info("Exiting. Goodbye!")
            sys.exit(0)
        else: print_error("Invalid option. Please try again.")

if __name__ == "__main__":
    main()