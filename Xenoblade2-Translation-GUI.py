import ttkbootstrap as tk
from ttkbootstrap import ttk, Style
from tkinter import filedialog, messagebox
import json
import os
import threading
import shutil
import configparser
from tkinter import font  # Keep this for now, might be needed for text height calculation
import re
import atexit
import sys
import subprocess

# --- New Global Variables ---
BASE_DIR = None
SECOND_BASE_DIR = None  # For translated files
CURRENT_JSON_PATH = None
CURRENT_ORIGINAL_JSON_PATH = None  # Path to original language file
FOLDER_STATUS = {}  # Dictionary to store folder status (color)
CURRENT_JSON_DATA = None
CURRENT_ORIGINAL_JSON_DATA = None  # Original language data
TREE = None  # global tree variable
UNSAVED_CHANGES = False
GAME_VERSION = None  # 'Xenoblade2' or 'Xenoblade3'

# --- Helper Functions ---
def open_path(path):
    """Opens a file or directory in a cross-platform way."""
    try:
        if sys.platform == "win32":
            os.startfile(os.path.normpath(path))
        elif sys.platform == "darwin":  # macOS
            subprocess.run(['open', path], check=True)
        else:  # linux and other UNIX-like
            subprocess.run(['xdg-open', path], check=True)
    except (OSError, subprocess.CalledProcessError, FileNotFoundError) as e:
        messagebox.showerror("Error", f"Unable to open '{os.path.basename(path)}': {e}")


def load_json(filepath):
    """Loads JSON data from a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        messagebox.showerror("Error Loading JSON", str(e))
        return None

def save_json(filepath, data):
    """Saves JSON data to a file, replacing the appropriate field with 'edited_text'."""
    try:
        # First, create a copy of the data to avoid modifying the original
        data_copy = json.loads(json.dumps(data))

        for row in data_copy['rows']:
            if 'edited_text' in row:
                if GAME_VERSION == "Xenoblade2":
                    # For X2, save to 'name' field
                    row['name'] = row['edited_text']
                else:
                    if GAME_VERSION == "XenobladeX":
                        # For X, save to 'name' field
                        row['name'] = row['edited_text']
                    elif '<DBAF43F0>' in row:
                        # For X3, save to DBAF43F0 field
                        row['<DBAF43F0>'] = row['edited_text']
                    else:
                        # Fallback to last field
                        last_field = list(row.keys())[-1]
                        if last_field != 'edited_text':  # Skip if last field is edited_text itself
                            row[last_field] = row['edited_text']
                del row['edited_text']  # Remove the 'edited_text' field after saving

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_copy, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Success", "JSON saved successfully!")
        return True
    except Exception as e:
        messagebox.showerror("Error Saving JSON", str(e))
        return False

def show_character_counts(text_widget):
    """Show character counts for each line in a tooltip."""
    # Get the text and split by newlines
    text = text_widget.get("1.0", "end-1c")
    lines = text.split('\\n')

    # Create a tooltip window
    tooltip = tk.Toplevel(text_widget)
    tooltip.wm_overrideredirect(True)
    tooltip.wm_geometry("+%d+%d" % (text_widget.winfo_rootx(), text_widget.winfo_rooty() - 70))

    # Create labels for each line count
    for i, line in enumerate(lines):
        count = len(line)
        label = ttk.Label(tooltip, text=f"Line {i+1}: {count} chars", background="#FFFFE0")  # Light yellow background
        label.pack()

    # Update position when text widget moves
    def update_position():
        tooltip.wm_geometry("+%d+%d" % (text_widget.winfo_rootx(), text_widget.winfo_rooty() - 70))
        tooltip.after(100, update_position)

    update_position()

    # Destroy tooltip when text widget loses focus
    def destroy_tooltip(event=None):
        tooltip.destroy()

    text_widget.bind('<FocusOut>', destroy_tooltip)
    return tooltip

def check_line_length(filename, text):
    """Checks if any line in the text exceeds the character limit based on the filename.
    Ignores characters within square brackets."""
    if not text:
        return False

    if filename.startswith("bf"):
        limit = 55
    elif filename.startswith("campfev") or filename.startswith("fev") or filename.startswith("kizuna") or filename.startswith("qst") or filename.startswith("tlk"):
        limit = 41
    else:
        return False  # No limit defined for this filename

    lines = text.split('\\n')
    for line in lines:
        # Remove content within square brackets
        line = re.sub(r'\[.*?\]', '', line)
        if len(line) > limit:
            return True
    return False

def calculate_text_height(text, font, width):
    """Calculates the height of the text based on the font and width."""
    text_widget = tk.Text(root, font=font, width=width)
    text_widget.insert("1.0", text)
    text_widget.update_idletasks()  # Force update of the widget
    
    # Calculate total height needed
    total_lines = 1
    for line in text.split('\\n'):
        text_widget.delete("1.0", "end")
        text_widget.insert("1.0", line)
        text_widget.update_idletasks()
        bbox = text_widget.bbox("end")
        if bbox:
            total_lines += bbox[1] // bbox[3] if bbox[3] > 0 else 1
    
    line_height = font.metrics("linespace")
    height = total_lines * line_height
    
    text_widget.destroy()
    return height + 10  # Add extra padding

def populate_table(tree, original_data, translated_data):
    """Populates the Treeview table with JSON data from both original and translated files."""
    # Clear existing data
    for item in tree.get_children():
        tree.delete(item)

    def format_text(text):
        if not text:
            return ""
        # Convert to string to avoid errors with non-string types (e.g., numbers)
        text = str(text)
        # Replace special characters with visible representations
        text = text.replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')
        return text

    # Use the configured DataTable.Treeview style
    TREE.configure(style='DataTable.Treeview')

    # Use translated data if available, otherwise use original
    data = translated_data if translated_data else original_data
    
    if data and 'rows' in data:
        for idx, row in enumerate(data['rows']):
            # Get original text if available - always use last field in row
            original_text = ""
            if original_data and 'rows' in original_data and len(original_data['rows']) > idx:
                original_row = original_data['rows'][idx]
                original_text = list(original_row.values())[-1] if original_row else ''
            
            # Get translated text - always use last field in row
            translated_text = list(row.values())[-1] if row else ''

            item_id = tree.insert("", "end", values=(
                row.get('$id', ''),
                row.get('label', ''),
                format_text(original_text),
                format_text(translated_text)
            ))
            
            # Check line length and apply tag
            if CURRENT_JSON_PATH:
                filename = os.path.basename(CURRENT_JSON_PATH)
                if check_line_length(filename, format_text(translated_text)):
                    tree.item(item_id, tags=("red",))

            # Calculate text height for the "EDITED TEXT" column
            text = row.get('name', '')
            font_size = font_size_var.get()
            width = 200 // 7
            if root.winfo_exists():  # Only calculate height if root window exists
                font_style = font.Font(family="Calibri", size=font_size)
                height = calculate_text_height(text, font_style, width)
                s = ttk.Style()
                s.configure('Treeview', rowheight=int(height + 15))

# --- GUI Functions ---

def browse_base_dir():
    """Opens a directory dialog to select the base directory."""
    global BASE_DIR
    BASE_DIR = filedialog.askdirectory()
    if BASE_DIR:
        base_dir_label.config(text=f"Base Directory: {BASE_DIR}")
        populate_file_list()
        save_gui_state()  # Save the GUI state

def browse_second_base_dir():
    """Opens a directory dialog to select the second base directory."""
    global SECOND_BASE_DIR
    SECOND_BASE_DIR = filedialog.askdirectory()
    if SECOND_BASE_DIR:
        second_base_dir_label.config(text=f"Second Directory: {SECOND_BASE_DIR}")
        save_gui_state()  # Save the GUI state

# Add this at the top with other global variables
ORIGINAL_FILE_LIST = []

def filter_folders(event=None):
    """Filters folders based on search text."""
    search_text = search_var.get().lower()
    
    if not ORIGINAL_FILE_LIST:
        return
        
    # Clear the current view
    for item in file_list.get_children():
        file_list.delete(item)
    
    # Rebuild the tree from original list
    for folder in ORIGINAL_FILE_LIST:
        folder_name = folder['text'].lower()
        folder_matches = not search_text or search_text in folder_name
        
        # If folder matches or any child matches, show it
        if folder_matches or any(search_text in child['text'].lower() for child in folder['children']):
            # Check if folder has a color tag
            folder_tags = ()
            if folder['text'] in FOLDER_STATUS:
                folder_tags = (FOLDER_STATUS[folder['text']],)
            
            # Recreate the folder item
            folder_id = file_list.insert("", "end", 
                text=folder['text'], 
                values=folder['values'],
                tags=folder_tags
            )
            
            # Add matching children
            for child in folder['children']:
                if not search_text or search_text in child['text'].lower():
                    # Check if child has a color tag
                    child_tags = ()
                    rel_path = child['values'][1].replace(BASE_DIR + '\\', '').replace('\\', '/')
                    if rel_path in FOLDER_STATUS:
                        child_tags = (FOLDER_STATUS[rel_path],)
                    
                    child_id = file_list.insert(folder_id, "end", 
                        text=child['text'], 
                        values=child['values'],
                        tags=child_tags
                    )

def detect_game_version(base_dir):
    """Detects whether this is Xenoblade 2, 3 or X based on folder structure and bschema files."""
    # Check for Xenoblade 3 structure (has game/ and evt/ folders)
    game_path = os.path.join(base_dir, "game")
    evt_path = os.path.join(base_dir, "evt")
    
    if os.path.exists(game_path) and os.path.exists(evt_path):
        # Found Xenoblade 3 structure
        root.title("BDAT Translation Tool [X3]")
        return "Xenoblade3"
    
    # Check for Xenoblade X structure (Modern schema but direct bdat folders)
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path):
            # Check for bschema file
            bschema_path = os.path.join(item_path, f"{item}.bschema")
            if os.path.exists(bschema_path):
                try:
                    with open(bschema_path, 'r') as f:
                        bschema = json.load(f)
                        if "version" in bschema and isinstance(bschema["version"], dict) and "Legacy" in bschema["version"]:
                            root.title("BDAT Translation Tool [X2]")
                            return "Xenoblade2"
                        elif "version" in bschema and bschema["version"] == "Modern":
                            # Check if this is X or 3 by looking for game/evt folders
                            if not os.path.exists(game_path) and not os.path.exists(evt_path):
                                root.title("BDAT Translation Tool [X]")
                                return "XenobladeX"
                            else:
                                root.title("BDAT Translation Tool [X3]")
                                return "Xenoblade3"
                except:
                    continue
    root.title("BDAT Translation Tool [X2]")
    return "Xenoblade2"  # Default to XB2 if unsure

def populate_file_list():
    """Populates the file list with BDAT folders and JSON files."""
    global ORIGINAL_FILE_LIST, GAME_VERSION
    # Clear existing list
    for item in file_list.get_children():
        file_list.delete(item)

    if BASE_DIR and os.path.exists(BASE_DIR):
        ORIGINAL_FILE_LIST = []  # Reset the original list
        try:
            GAME_VERSION = detect_game_version(BASE_DIR)
        except Exception as e:
            messagebox.showerror("Error", f"Could not detect game version: {str(e)}")
            return

        if GAME_VERSION == "Xenoblade3":
            # Xenoblade 3 has game/ and evt/ folders
            for top_folder in ["game", "evt"]:
                top_folder_path = os.path.join(BASE_DIR, top_folder)
                if os.path.exists(top_folder_path):
                    for bdat_folder in os.listdir(top_folder_path):
                        bdat_folder_path = os.path.join(top_folder_path, bdat_folder)
                        if os.path.isdir(bdat_folder_path):
                            folder_id = file_list.insert("", "end", text=f"{top_folder}/{bdat_folder}", values=("folder", bdat_folder_path))
                            ORIGINAL_FILE_LIST.append({
                                'id': folder_id,
                                'text': f"{top_folder}/{bdat_folder}",
                                'values': ("folder", bdat_folder_path),
                                'children': []
                            })
                            
                            if bdat_folder in FOLDER_STATUS:
                                file_list.item(folder_id, tags=(FOLDER_STATUS[bdat_folder],))

                            inner_folder_path = os.path.join(bdat_folder_path, bdat_folder)
                            if os.path.isdir(inner_folder_path):
                                json_files = [f for f in os.listdir(inner_folder_path) if f.endswith(".json")]
                                for json_file in json_files:
                                    json_path = os.path.join(inner_folder_path, json_file)
                                    child_id = file_list.insert(folder_id, "end", text=json_file, values=("file", json_path))
                                    ORIGINAL_FILE_LIST[-1]['children'].append({
                                        'id': child_id,
                                        'text': json_file,
                                        'values': ("file", json_path)
                                    })
        else:
            # Xenoblade 2 has direct bdat folders
            for bdat_folder in os.listdir(BASE_DIR):
                bdat_folder_path = os.path.join(BASE_DIR, bdat_folder)
                if os.path.isdir(bdat_folder_path):
                    folder_id = file_list.insert("", "end", text=bdat_folder, values=("folder", bdat_folder_path))
                    ORIGINAL_FILE_LIST.append({
                        'id': folder_id,
                        'text': bdat_folder,
                        'values': ("folder", bdat_folder_path),
                        'children': []
                    })
                    
                    if bdat_folder in FOLDER_STATUS:
                        file_list.item(folder_id, tags=(FOLDER_STATUS[bdat_folder],))

                    inner_folder_path = os.path.join(bdat_folder_path, bdat_folder)
                    if os.path.isdir(inner_folder_path):
                        json_files = [f for f in os.listdir(inner_folder_path) if f.endswith(".json")]
                        for json_file in json_files:
                            json_path = os.path.join(inner_folder_path, json_file)
                            child_id = file_list.insert(folder_id, "end", text=json_file, values=("file", json_path))
                            ORIGINAL_FILE_LIST[-1]['children'].append({
                                'id': child_id,
                                'text': json_file,
                                'values': ("file", json_path)
                            })


def load_table_data(json_path):
    """Loads the selected JSON file into the table."""
    global CURRENT_JSON_PATH, CURRENT_JSON_DATA, CURRENT_ORIGINAL_JSON_PATH, CURRENT_ORIGINAL_JSON_DATA, GAME_VERSION

    CURRENT_JSON_PATH = json_path
    CURRENT_JSON_DATA = load_json(CURRENT_JSON_PATH)
    
    # Find corresponding file in second base dir if it exists
    CURRENT_ORIGINAL_JSON_DATA = None
    if SECOND_BASE_DIR:
        # Get relative path from first base dir
        rel_path = os.path.relpath(json_path, BASE_DIR)
        # Build path in second base dir
        original_path = os.path.join(SECOND_BASE_DIR, rel_path)
        if os.path.exists(original_path):
            CURRENT_ORIGINAL_JSON_PATH = original_path
            CURRENT_ORIGINAL_JSON_DATA = load_json(original_path)
        elif GAME_VERSION in ["Xenoblade3", "XenobladeX"]:
            # For XB3, also check if the file exists in the other top-level folder (game/evt)
            parts = rel_path.split(os.sep)
            if len(parts) > 1 and parts[0] in ["game", "evt"]:
                # Try the opposite folder
                opposite_folder = "evt" if parts[0] == "game" else "game"
                opposite_path = os.path.join(SECOND_BASE_DIR, opposite_folder, *parts[1:])
                if os.path.exists(opposite_path):
                    CURRENT_ORIGINAL_JSON_PATH = opposite_path
                    CURRENT_ORIGINAL_JSON_DATA = load_json(opposite_path)
    
    if CURRENT_JSON_DATA:
        populate_table(TREE, CURRENT_ORIGINAL_JSON_DATA, CURRENT_JSON_DATA)

def file_list_select(event):
    """Handles selection in the file list."""
    global CURRENT_JSON_PATH, UNSAVED_CHANGES

    # Check for unsaved changes before proceeding
    if UNSAVED_CHANGES and CURRENT_JSON_PATH:
        response = messagebox.askyesnocancel("Warning", "You have unsaved changes. Do you want to save them?", icon='warning')
        if response is True:  # Yes, save changes
            save_table_data()
        elif response is None:  # Cancel
            return  # Do nothing, stay on the current file

    selected_item = file_list.selection()
    if not selected_item:
        return

    item_type = file_list.item(selected_item, 'values')[0]
    item_path = file_list.item(selected_item, 'values')[1]

    if item_type == "file":
        load_table_data(item_path)
    elif item_type == "folder":
        # Load the first JSON file in the folder
        inner_folder_path = os.path.join(item_path, os.path.basename(item_path))
        if os.path.isdir(inner_folder_path):
            json_files = [f for f in os.listdir(inner_folder_path) if f.endswith(".json")]
            if json_files:
                first_json_path = os.path.join(inner_folder_path, json_files[0])
                load_table_data(first_json_path)
    
    UNSAVED_CHANGES = False  # Reset the flag after loading new data

def save_table_data():
    """Saves the edited data back to the JSON file."""
    global CURRENT_JSON_PATH, CURRENT_JSON_DATA, UNSAVED_CHANGES

    if not CURRENT_JSON_PATH or not CURRENT_JSON_DATA:
        messagebox.showerror("Error", "No JSON file loaded.")
        return

    # Get data from the treeview
    for index, item in enumerate(TREE.get_children()):
        try:
            edited_text = TREE.item(item)['values'][3]  # Get the value from the translated text column
            # Convert visible special characters back to actual characters
            if edited_text is not None:
                if not isinstance(edited_text, str):
                    print(f"Problem in row {index}: Found non-string value (type={type(edited_text)}), converting to string. Content={repr(edited_text)}")  # Debug output
                    edited_text = str(edited_text)
                edited_text = edited_text.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
            
            if CURRENT_JSON_DATA and 'rows' in CURRENT_JSON_DATA and len(CURRENT_JSON_DATA['rows']) > index:
                row = CURRENT_JSON_DATA['rows'][index]
                row['edited_text'] = edited_text
        except Exception as e:
            print(f"Error in row {index}: {str(e)}. Value type={type(edited_text)}, Content={repr(edited_text)}")  # Debug output
            raise  # Re-raise the exception after logging it

    save_json(CURRENT_JSON_PATH, CURRENT_JSON_DATA)
    UNSAVED_CHANGES = False  # Reset the flag after saving

def undo_changes():
    """Reloads the original JSON data into the table, discarding changes."""
    global CURRENT_JSON_PATH, CURRENT_JSON_DATA, CURRENT_ORIGINAL_JSON_DATA, UNSAVED_CHANGES
    if CURRENT_JSON_PATH:
        # Reload the JSON data
        CURRENT_JSON_DATA = load_json(CURRENT_JSON_PATH)
        if CURRENT_JSON_DATA:
            # Repopulate the table with original and translated data
            populate_table(TREE, CURRENT_ORIGINAL_JSON_DATA, CURRENT_JSON_DATA)
            messagebox.showinfo("Info", "Changes undone. Table reloaded from file.")
            UNSAVED_CHANGES = False  # Reset the flag after undo
    else:
        messagebox.showinfo("Info", "No file loaded.")

def edit_cell(event):
    """Handles cell editing in the Treeview."""
    global UNSAVED_CHANGES
    if not UNSAVED_CHANGES:
        UNSAVED_CHANGES = True  # Set flag on first edit
    for item in TREE.selection():
        # Identify column and row
        column = TREE.identify_column(event.x)
        row = TREE.identify_row(event.y)

        # Get column id
        column_id = int(column[1:]) - 1

        # Only allow editing of the "EDITED TEXT" column (column 4)
        if column_id == 3:
            # Get bounding box of the cell
            x, y, width, height = TREE.bbox(item, column)

            # Get current value of the cell (already formatted)
            value = TREE.item(item, 'values')[column_id]

            # Create a text widget for multiline editing
            font_size = font_size_var.get()
            font_style = font.Font(family="Calibri", size=font_size)
            # Calculate needed height based on text content
            text_height = calculate_text_height(value, font_style, width)
            height = max(text_height // 20, 4)  # Convert pixels to lines, minimum 4 lines
            
            # Create text widget with proper sizing
            text_widget = tk.Text(TREE, 
                                width=width//7, 
                                height=height, 
                                background="#FFFFE0", 
                                font=font_style,
                                wrap=tk.WORD)  # Enable word wrapping
            # Display escaped special characters for editing
            edit_value = value.replace('\n', '\\n')
            text_widget.insert("1.0", edit_value)
            # Ensure the edit window is visible and properly sized
            text_widget.place(x=x, y=y, width=max(width, 100), height=max(height*20, 80))  # Minimum reasonable sizes
            text_widget.focus()

            # Show character counts
            tooltip = show_character_counts(text_widget)

            def save_value(event=None):
                # Get the text and convert special characters back to visible format
                new_value = text_widget.get("1.0", "end-1c")
                formatted_value = new_value.replace('\n', '\\n').replace('\t', '\t').replace('\r', '\r')

                # Update the tree values
                values = list(TREE.item(item, 'values'))
                values[column_id] = formatted_value  # Store formatted version
                TREE.item(item, values=values)
                UNSAVED_CHANGES = True  # Set the flag when a change is made

                # Check line length and apply tag
                if CURRENT_JSON_PATH:
                    filename = os.path.basename(CURRENT_JSON_PATH)
                    if check_line_length(filename, formatted_value):
                        TREE.item(item, tags=("red",))
                    else:
                        TREE.item(item, tags=())  # Remove the tag if it exists

                # Update row height
                font_size = font_size_var.get()
                font_style = font.Font(family="Calibri", size=font_size)
                height = calculate_text_height(formatted_value, font_style, width//7)
                s = ttk.Style()
                s.configure('Treeview', rowheight=int(height + 15))
                
                text_widget.destroy()
                tooltip.destroy()
            
            # This function handles paste events manually to fix a bug on some Linux systems
            # where selected text is not replaced upon pasting.
            def custom_paste(event=None):
                try:
                    # Get the content from the clipboard
                    clipboard_content = text_widget.clipboard_get()
                    
                    # Check if there is any selected text
                    if text_widget.tag_ranges("sel"):
                        # If so, delete the selected text first
                        text_widget.delete("sel.first", "sel.last")
                    
                    # Insert the clipboard content at the current cursor position
                    text_widget.insert(tk.INSERT, clipboard_content)
                    
                    # Trigger the character count update
                    update_counts()

                except tk.TclError:
                    # This can happen if the clipboard is empty or contains non-text data.
                    pass 
                
                # Return "break" to prevent the default (and potentially buggy)
                # paste binding from running and causing duplication.
                return "break"

            # Bind the custom paste function to the paste event
            text_widget.bind("<<Paste>>", custom_paste)

            # Bind enter key to save the value
            text_widget.bind('<Return>', save_value)
            text_widget.bind('<Control-Return>', lambda e: text_widget.insert(tk.INSERT, '\n'))

            # Bind focus out to save the value and destroy the text widget
            text_widget.bind('<FocusOut>', save_value)

            # Bind escape key to cancel editing
            def cancel_edit(event):
                text_widget.destroy()
                tooltip.destroy()
            text_widget.bind('<Escape>', cancel_edit)

            # Update character counts while typing
            def update_counts(event=None):
                try:
                    # Update the tooltip with new counts
                    text = text_widget.get("1.0", "end-1c")
                    # Split by actual newlines (from pressing Enter) and properly escaped \n
                    lines = []
                    temp_lines = []
                    # First split by actual newlines
                    for part in text.split('\n'):
                        # Then split by properly escaped \n (not just backslash)
                        temp_lines.extend(part.split('\\n'))
                    
                    # Now properly handle the split parts
                    for line in temp_lines:
                        # Only add non-empty lines
                        if line.strip():
                            lines.append(line)
                    
                    # Clear existing labels and create new ones
                    for child in tooltip.winfo_children():
                        child.destroy()
                    
                    # Create new labels for each line
                    for i, line in enumerate(lines):
                        count = len(line)
                        label = ttk.Label(tooltip, text=f"Line {i+1}: {count} chars", background="#FFFFE0")
                        label.pack()
                except:
                    pass
                return True
            
            text_widget.bind('<KeyRelease>', update_counts)

def mark_folder(status):
    """Marks the selected folder or file with a background color."""
    selected_item = file_list.selection()
    if not selected_item:
        messagebox.showinfo("Info", "Please select a folder or file.")
        return

    item_text = file_list.item(selected_item, 'text')
    item_path = file_list.item(selected_item, 'values')[1]
    item_type = file_list.item(selected_item, 'values')[0]

    if status == "green":
        color = "green"
    elif status == "orange":
        color = "orange"
    else:
        color = ""  # Set color to empty string to clear the tag

    # For files, store relative path from the BDAT folder
    if item_type == "file":
        # Get the BDAT folder name (parent folder)
        bdat_folder = os.path.basename(os.path.dirname(os.path.dirname(item_path)))
        # Get relative path within BDAT folder
        rel_path = os.path.relpath(item_path, os.path.join(BASE_DIR, bdat_folder))
        # Convert to forward slashes for consistency
        key = rel_path.replace('\\', '/')
    else:
        # For folders, just use the folder name
        key = item_text

    # Update the status in the dictionary
    if key:
        if status:
            FOLDER_STATUS[key] = status  # Store the status
        else:
            FOLDER_STATUS.pop(key, None)  # Remove the item from the status if clearing

        # Apply the tag to the selected item
        file_list.item(selected_item, tags=(color,))

        save_config()  # Save the configuration

def load_config():
    """Loads the folder and file status from the config file."""
    global FOLDER_STATUS
    config = configparser.ConfigParser()
    config_path = os.path.join(BASE_DIR, "translation_config.ini")

    try:
        config.read(config_path)
        if 'FOLDER_STATUS' in config:
            FOLDER_STATUS = {k: v for k, v in config['FOLDER_STATUS'].items()}
    except Exception as e:
        print(f"Error loading config: {e}")

    # Apply colors to both folders and files based on loaded config
    for item in file_list.get_children():
        item_text = file_list.item(item, 'text')
        item_path = file_list.item(item, 'values')[1]
        item_type = file_list.item(item, 'values')[0]

        # Get relative path from BASE_DIR
        rel_path = os.path.relpath(item_path, BASE_DIR)
        key = rel_path.replace('\\', '/')

        if key in FOLDER_STATUS:
            file_list.item(item, tags=(FOLDER_STATUS[key],))

def save_config():
    """Saves the folder status to the config file."""
    config = configparser.ConfigParser()
    config['FOLDER_STATUS'] = FOLDER_STATUS
    config_path = os.path.join(BASE_DIR, "translation_config.ini")

    try:
        with open(config_path, 'w') as configfile:
            config.write(configfile)
    except Exception as e:
        print(f"Error saving config: {e}")

def save_gui_state():
    """Saves the GUI state (base directories) to the config file."""
    config = configparser.ConfigParser()
    config['GUI_STATE'] = {
        'base_dir': BASE_DIR if BASE_DIR else "",
        'second_base_dir': SECOND_BASE_DIR if SECOND_BASE_DIR else ""
    }
    # Add quotes around the values
    for key in config['GUI_STATE']:
        config['GUI_STATE'][key] = f"\"{config['GUI_STATE'][key]}\""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    config_path = os.path.join(script_dir, f"{script_name}.ini")  # Save in the same directory as the script

    try:
        with open(config_path, 'w') as configfile:
            config.write(configfile)
    except Exception as e:
        print(f"Error saving GUI state: {e}")

def load_gui_state():
    """Loads the GUI state (base directories) from the config file."""
    global BASE_DIR, SECOND_BASE_DIR
    config = configparser.ConfigParser()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    config_path = os.path.join(script_dir, f"{script_name}.ini")

    try:
        config.read(config_path)
        if 'GUI_STATE' in config:
            BASE_DIR = config['GUI_STATE'].get('base_dir', "").strip('"')
            SECOND_BASE_DIR = config['GUI_STATE'].get('second_base_dir', "").strip('"')

            # Normalize paths and ensure they exist
            if BASE_DIR and os.path.exists(BASE_DIR):
                BASE_DIR = os.path.normpath(BASE_DIR)
                print(f"Loaded BASE_DIR: {BASE_DIR}")
                base_dir_label.config(text=f"Base Directory: {BASE_DIR}")
            else:
                BASE_DIR = None
                print("BASE_DIR path does not exist or is invalid")

            if SECOND_BASE_DIR and os.path.exists(SECOND_BASE_DIR):
                SECOND_BASE_DIR = os.path.normpath(SECOND_BASE_DIR)
                print(f"Loaded SECOND_BASE_DIR: {SECOND_BASE_DIR}")
                second_base_dir_label.config(text=f"Second Directory: {SECOND_BASE_DIR}")
            else:
                SECOND_BASE_DIR = None
                print("SECOND_BASE_DIR path does not exist or is invalid")

    except Exception as e:
        print(f"Error loading GUI state: {e}")
    print(f"Config file path: {config_path}")

# --- GUI Setup ---
root = tk.Window(themename='flatly')
root.title("BDAT Translation Tool")
# Set default font size for the application
default_font = ('Calibri', 12)
root.option_add('*Font', default_font)
root.option_add('*TCombobox*Font', default_font)
root.option_add('*TEntry*Font', default_font)
root.option_add('*TLabel*Font', default_font)

# Call save_gui_state when the window is closed
root.protocol("WM_DELETE_WINDOW", lambda: [save_gui_state(), root.destroy()])

# Ensure we only have one window
root.withdraw()
root.deiconify()

# --- Top Frame (Directory/File Navigation and Buttons) ---
top_frame = ttk.Frame(root, padding=10)
top_frame.pack(side=tk.TOP, fill=tk.X)

# Search filter
search_frame = ttk.Frame(top_frame)
search_frame.pack(side=tk.LEFT, padx=5, pady=5)

search_label = ttk.Label(search_frame, text="Search:")
search_label.pack(side=tk.LEFT)

search_var = tk.StringVar()
search_entry = ttk.Entry(search_frame, textvariable=search_var, width=20)
search_entry.pack(side=tk.LEFT, padx=5)
search_entry.bind('<KeyRelease>', filter_folders)

def update_font_size(event=None):
    """Updates the font size and repopulates the table."""
    font_size = font_size_var.get()
    if root.winfo_exists():  # Only update if root window exists
        # Update the data table style
        style = ttk.Style()
        style.configure('DataTable.Treeview', font=('Calibri', font_size))
        
        # Calculate and set new row height
        font_style = font.Font(family="Calibri", size=font_size)
        new_height = calculate_text_height("Sample Text", font_style, 200//7)
        style.configure('DataTable.Treeview', rowheight=int(new_height + 15))
        
        # Apply the style to the treeview
        TREE.configure(style='DataTable.Treeview')
        
        # Force refresh of the treeview
        TREE.update_idletasks()
        
        # Repopulate table if data is loaded
        if CURRENT_JSON_PATH and CURRENT_ORIGINAL_JSON_DATA and CURRENT_JSON_DATA:
            populate_table(TREE, CURRENT_ORIGINAL_JSON_DATA, CURRENT_JSON_DATA)



base_dir_button = ttk.Button(top_frame, text="Select Base Dir", command=browse_base_dir)
base_dir_button.pack(side=tk.LEFT, padx=5, pady=5)

base_dir_label = ttk.Label(top_frame, text="Base Directory: None")
base_dir_label.pack(side=tk.LEFT, padx=5, pady=5)

second_base_dir_button = ttk.Button(top_frame, text="Select Second Dir", command=browse_second_base_dir)
second_base_dir_button.pack(side=tk.LEFT, padx=5, pady=5)

second_base_dir_label = ttk.Label(top_frame, text="Second Directory: None")
second_base_dir_label.pack(side=tk.LEFT, padx=5, pady=5)

# --- Panedwindow for Left/Right Sections ---
paned_window = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
paned_window.pack(fill=tk.BOTH, expand=True)

# --- Left Frame (File List) ---
left_frame = ttk.Frame(paned_window, padding=10)
paned_window.add(left_frame)

# --- File List with Scrollbar ---
file_list_frame = ttk.Frame(left_frame)
file_list_frame.pack(fill=tk.BOTH, expand=True)

file_list_scrollbar = ttk.Scrollbar(file_list_frame)
file_list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

file_list = ttk.Treeview(file_list_frame, columns=("Type", "Path"), yscrollcommand=file_list_scrollbar.set, style='FileList.Treeview')
file_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
file_list.heading("#0", text="Folders/Files", anchor=tk.W)
file_list.heading("Type", text="Type")
file_list.column("Type", width=50, stretch=False)
file_list.column("Path", width=0, stretch=False)  # Hide the path column
file_list.bind("<Double-1>", file_list_select)  # Double-click to load

def open_translated_dir(event=None):
    selected_item = file_list.selection()
    if selected_item:
        item_type = file_list.item(selected_item, 'values')[0]
        item_path = file_list.item(selected_item, 'values')[1]
        if item_type == "folder":
            inner_folder_path = os.path.join(item_path, os.path.basename(item_path))
            open_path(inner_folder_path)
        elif item_type == "file":
            open_path(os.path.dirname(item_path))

def open_original_dir(event=None):
    selected_item = file_list.selection()
    if selected_item:
        item_type = file_list.item(selected_item, 'values')[0]
        item_path = file_list.item(selected_item, 'values')[1]
        
        # Check if a second base directory is set
        if SECOND_BASE_DIR:
            # Get the relative path from the base directory
            rel_path = os.path.relpath(item_path, BASE_DIR)
            # Construct the path in the second base directory
            original_path = os.path.join(SECOND_BASE_DIR, rel_path)
            
            # Check if the item is a folder or a file
            if item_type == "folder":
                inner_original_path = os.path.join(original_path, os.path.basename(original_path))
                # Check if the directory exists in the second base directory
                if os.path.isdir(inner_original_path):
                    open_path(inner_original_path)
                else:
                    messagebox.showinfo("Info", "Original directory not found.")
            elif item_type == "file":
                # Check if the file exists in the second base directory
                if os.path.isfile(original_path):
                    open_path(os.path.dirname(original_path))
                else:
                    messagebox.showinfo("Info", "Original file/directory not found.")
        else:
            messagebox.showinfo("Info", "Second base directory not set.")

def show_context_menu(event):
    selected_item = file_list.selection()
    if selected_item:
        context_menu.post(event.x_root, event.y_root)

# Create context menu
context_menu = tk.Menu(root, tearoff=0)
context_menu.add_command(label="Open Translated JSON Directory", command=open_translated_dir)
context_menu.add_command(label="Open Original JSON Directory", command=open_original_dir)

# Bind right click to show context menu
file_list.bind("<Button-3>", show_context_menu)

file_list_scrollbar.config(command=file_list.yview)

# Configure styles with consistent font sizes
style = ttk.Style()
style.configure('FileList.Treeview', font=('Calibri', 12, 'bold'))  # Bold style for file list
style.configure('DataTable.Treeview', font=('Calibri', 12))  # Regular style for data table

# --- Define tags for background colors ---
file_list.tag_configure("green", background="green")
file_list.tag_configure("orange", background="orange")
file_list.tag_configure("red", background="red")

# --- Right Frame (Table Editor) ---
right_frame = ttk.Frame(paned_window, padding=10)
paned_window.add(right_frame)

# --- Buttons ---
button_frame = ttk.Frame(right_frame)
button_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

save_button = ttk.Button(button_frame, text="Save", command=save_table_data, bootstyle="primary")
save_button.pack(side=tk.LEFT, padx=5, pady=5)

undo_button = ttk.Button(button_frame, text="Undo", command=undo_changes, bootstyle="warning")
undo_button.pack(side=tk.LEFT, padx=5, pady=5)

# Font Size Selection
font_size_label = ttk.Label(button_frame, text="Font Size:")
font_size_label.pack(side=tk.LEFT, padx=(10,0))

font_size_var = tk.IntVar(value=12)  # Default font size
font_size_combo = ttk.Combobox(button_frame, textvariable=font_size_var, values=[8, 10, 12, 14, 16], width=3)
font_size_combo.pack(side=tk.LEFT, padx=5)
font_size_combo.bind("<<ComboboxSelected>>", update_font_size)

mark_green_button = ttk.Button(button_frame, text="Mark Green", command=lambda: mark_folder("green"), bootstyle="success")
mark_green_button.pack(side=tk.LEFT, padx=5, pady=5)

mark_orange_button = ttk.Button(button_frame, text="Mark Orange", command=lambda: mark_folder("orange"), bootstyle="warning")
mark_orange_button.pack(side=tk.LEFT, padx=5, pady=5)

clear_color_button = ttk.Button(button_frame, text="Clear Color", command=lambda: mark_folder(None), bootstyle="secondary")
clear_color_button.pack(side=tk.LEFT, padx=5, pady=5)

# --- Treeview Table ---
style = ttk.Style()
style.configure('Treeview', rowheight=40)

TREE = ttk.Treeview(
    right_frame, 
    columns=("ID", "LABEL", "ORIGINAL TEXT", "TRANSLATED TEXT"), 
    show="headings", 
    style='DataTable.Treeview'
)
TREE.heading("ID", text="ID")
TREE.heading("LABEL", text="LABEL")
TREE.heading("ORIGINAL TEXT", text="ORIGINAL TEXT")
TREE.heading("TRANSLATED TEXT", text="TRANSLATED TEXT")

# Set column widths with stretch for text columns
TREE.column("ID", width=50, stretch=False)
TREE.column("LABEL", width=150, stretch=False)
TREE.column("ORIGINAL TEXT", width=200, stretch=True, anchor=tk.W)
TREE.column("TRANSLATED TEXT", width=200, stretch=True, anchor=tk.W)

# Add a Scrollbar to the Treeview Table
tree_scroll = ttk.Scrollbar(right_frame, orient="vertical", command=TREE.yview)
TREE.configure(yscrollcommand=tree_scroll.set)
tree_scroll.pack(side="right", fill="y")
TREE.pack(fill=tk.BOTH, expand=True)

# Define tag for red background
TREE.tag_configure("red", background="red")

# Bind double click to edit cell
TREE.bind("<Double-1>", edit_cell)

def copy_cell_value():
    """Copies the value of the selected cell to the clipboard."""
    item = TREE.selection()[0]  # Get the selected item
    column_id = int(TREE.identify_column(event.x)[1:]) - 1  # Get the column ID
    value = TREE.item(item, 'values')[column_id]  # Get the cell value
    root.clipboard_clear()
    root.clipboard_append(value)
    root.update()

def show_tree_context_menu(event):
    """Shows the context menu for the Treeview."""
    for item in TREE.selection():
        tree_context_menu.post(event.x_root, event.y_root)

# Create context menu for the Treeview
tree_context_menu = tk.Menu(root, tearoff=0)
tree_context_menu.add_command(label="Copy Cell Value", command=lambda: copy_cell_value())

def show_tree_context_menu(event):
    """Shows the context menu for the Treeview."""
    tree_context_menu.post(event.x_root, event.y_root)
    global context_menu_event
    context_menu_event = event

def copy_cell_value():
    """Copies the value of the selected cell to the clipboard."""
    item = TREE.selection()[0]  # Get the selected item
    column_id = int(TREE.identify_column(context_menu_event.x)[1:]) - 1  # Get the column ID
    value = TREE.item(item, 'values')[column_id]  # Get the cell value
    root.clipboard_clear()
    root.clipboard_append(value)
    root.update()

# Bind right click to show context menu
TREE.bind("<Button-3>", show_tree_context_menu)

# Load GUI state on startup
load_gui_state()

# Load config after GUI state is loaded and BASE_DIR is set
if BASE_DIR:
    print(f"Loading config from: {os.path.join(BASE_DIR, 'translation_config.ini')}")
    load_config()
    # Apply colors to folders based on loaded config
    for item in file_list.get_children():
        folder_name = file_list.item(item, 'text')
        if folder_name in FOLDER_STATUS:
            file_list.item(item, tags=(FOLDER_STATUS[folder_name],))
    populate_file_list()  # Ensure the file list is populated with the correct colors
    
    # Apply colors to files after populating the file list
    for item in file_list.get_children():
        item_type = file_list.item(item, 'values')[0]
        if item_type == "folder":
            for child in file_list.get_children(item):
                child_path = file_list.item(child, 'values')[1]
                # Get the BDAT folder name (parent folder)
                bdat_folder = os.path.basename(os.path.dirname(os.path.dirname(child_path)))
                # Get relative path within BDAT folder
                rel_path = os.path.relpath(child_path, os.path.join(BASE_DIR, bdat_folder))
                # Convert to forward slashes for consistency
                key = rel_path.replace('\\', '/')
                if key in FOLDER_STATUS:
                    file_list.item(child, tags=(FOLDER_STATUS[key],))

def delayed_populate():
    # Select the first item in the file list if there are any
    first_item = file_list.get_children()
    if first_item:
        file_list.selection_set(first_item[0])
        file_list.event_generate("<<TreeviewSelect>>")  # Trigger the select event

root.after(100, delayed_populate)  # Delay the population

root.mainloop()
