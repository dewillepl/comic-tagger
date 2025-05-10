import shutil
import re
import os # For os.path.basename, os.path.dirname if needed by utils
import sys

# --- ANSI Escape Codes for Styling ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    # Colors (foreground)
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BRIGHT_BLACK = "\033[90m" # Dim text

# --- General Utility Functions ---

def print_error(message, to_stderr=True):
    """Prints a styled error message."""
    output_stream = sys.stderr if to_stderr else sys.stdout
    print(f"{Style.RED}Error: {message}{Style.RESET}", file=output_stream)

def print_info(message, to_stderr=True):
    """Prints a styled informational message."""
    output_stream = sys.stderr if to_stderr else sys.stdout
    # Using stderr for info messages is common for CLI tools to separate from data output
    print(f"{Style.YELLOW}Info: {message}{Style.RESET}", file=output_stream)

def print_success(message, to_stderr=False): # Success messages usually go to stdout
    """Prints a styled success message."""
    output_stream = sys.stderr if to_stderr else sys.stdout
    print(f"{Style.GREEN}Success: {message}{Style.RESET}", file=output_stream)

def strip_html(html_string):
    """Removes HTML tags from a string and decodes common entities."""
    if not html_string:
        return ""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', html_string)
    # Decode common HTML entities
    entities = {
        ' ': ' ', '&': '&', '<': '<', '>': '>',
        '"': '"', ''': "'", ''': "'" 
        # Add more entities if needed
    }
    for entity, char in entities.items():
        clean = clean.replace(entity, char)
    return clean.strip()

def make_clickable_link(url, text=None):
    """Creates a terminal hyperlink if the URL is valid."""
    if not url or not isinstance(url, str) or not (url.startswith('http://') or url.startswith('https://')):
        # If no URL or invalid, just return the text (or URL as text)
        return text if text else (url if url else "")

    if text is None:
        text = url
    # OSC 8 ; params ; URI ST (ESC]8;;linkESC\textESC]8;;ESC\)
    return f"\033]8;;{url}\a{Style.BLUE}{Style.UNDERLINE}{text}{Style.RESET}\033]8;;\a"

def print_header_line(title, char="=", color=Style.MAGENTA):
    """Prints a full-width styled header line."""
    try:
        term_width = shutil.get_terminal_size((80, 20)).columns
    except OSError: # Fallback if terminal size can't be determined (e.g., not a real TTY)
        term_width = 80
        
    title_text = f" {title} "
    padding_total = term_width - len(title_text)
    padding_left = padding_total // 2
    padding_right = padding_total - padding_left
    
    # Ensure padding is not negative
    padding_left = max(0, padding_left)
    padding_right = max(0, padding_right)

    header = f"{char * padding_left}{title_text}{char * padding_right}"
    # Ensure header doesn't exceed terminal width due to rounding or very long titles
    header = header[:term_width] 
    print(f"\n{Style.BOLD}{color}{header}{Style.RESET}")


def print_field(label, value, indent=0, is_url=False, url_text=None, 
                value_style="", label_color=Style.CYAN, value_color="", 
                label_width=18): # Added label_width
    """Prints a styled field (label: value) with fixed label width."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        value_display = f"{Style.BRIGHT_BLACK}(not available){Style.RESET}"
    elif is_url:
        value_display = make_clickable_link(str(value), text=url_text if url_text else str(value))
    else:
        value_display = f"{value_style}{value_color}{value}{Style.RESET}"
    
    indent_space = "  " * indent
    # Use f-string for padding the label to label_width
    print(f"{indent_space}{Style.BOLD}{label_color}{label:<{label_width}}{Style.RESET} {value_display}")


def print_multiline_text(label, text, indent=0, label_color=Style.CYAN, label_width=18):
    """Prints a label and then wraps text for readability."""
    cleaned_text = strip_html(text) # Ensure text is cleaned
    
    indent_space = "  " * indent
    text_indent_str = '  ' * (indent + 1)

    if not cleaned_text:
        # Print label with "(not available)" if text is empty after cleaning
        print(f"{indent_space}{Style.BOLD}{label_color}{label:<{label_width}}{Style.RESET} {Style.BRIGHT_BLACK}(not available){Style.RESET}")
        return

    # Print the label part first
    print(f"{indent_space}{Style.BOLD}{label_color}{label:<{label_width}}{Style.RESET}")
    
    try:
        terminal_width = shutil.get_terminal_size((80, 20)).columns
    except OSError:
        terminal_width = 80
        
    wrap_width = terminal_width - len(text_indent_str)
    if wrap_width <= 0: # Handle very narrow terminals
        wrap_width = 20 # A small positive fallback

    current_line = ""
    for paragraph in cleaned_text.splitlines(): # Handle existing newlines
        if not paragraph.strip():
            print(text_indent_str) # Print an empty indented line for paragraph breaks
            continue
        words = paragraph.split()
        for word in words:
            if len(current_line) + len(word) + 1 > wrap_width:
                print(f"{text_indent_str}{current_line}")
                current_line = word
            else:
                if current_line: current_line += " " + word
                else: current_line = word
        if current_line:
            print(f"{text_indent_str}{current_line}")
            current_line = ""

# Note: The `natural_sort_key_for_convert` was specific to convert_files.py's image sorting needs.
# If natsort.natsort_keygen() is needed elsewhere, it can be imported directly in those modules.
# For now, keeping utils focused on very generic helpers.
# If more complex shared data structures or models emerge, they could also go here or in a 'models.py'.