import numpy as np
import cv2
import easyocr
import ctypes
import wx
import time
import sys
import re
from PIL import ImageGrab
import os

# Define the area for the screenshot
x1, y1 = 524, 84
x2, y2 = 1390, 1010

# Virtual key codes
VK_F5 = 0x74  # Key code for 'F5'
VK_CONTROL = 0x11
VK_E = 0x45  # Key code for 'E'

# Get reference to user32.dll for keyboard input
user32 = ctypes.windll.user32

reader = None

is_editing = False

def initialize_ocr():
    global reader
    print("Initializing EasyOCR (this may take a moment)...")
    reader = easyocr.Reader(['en'])
    print("OCR Ready!")

def clean_poi_name(text):
    """
    Cleans a POI name:
    - Keeps only letters (no numbers), spaces and basic punctuation
    - Removes numbers and other symbols
    """
    # Keep letters, spaces, and basic punctuation
    return re.sub(r'[^A-Za-z_\s.,\'-]', '', text).strip()

def process_screenshot():
    global reader
    
    if reader is None:
        initialize_ocr()
    
    print("Capturing screenshot...")
    # Take a screenshot of the specified area
    screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
    
    # Convert PIL image to numpy array for EasyOCR
    img_np = np.array(screenshot)
    
    print("Running OCR on screenshot...")
    # Run OCR directly on the color image
    results = reader.readtext(img_np)
    
    # Process results to get POI format
    pois = []
    for (bbox, text, prob) in results:
        if prob > 0.5:  # Filter by confidence
            # Calculate center position relative to the original screen
            center_x = int((bbox[0][0] + bbox[2][0]) / 2) + x1
            center_y = int((bbox[0][1] + bbox[2][1]) / 2) + y1
            
            # Clean up text and filter for all caps
            clean_text = text.strip()
            
            # Only include text that is already in all caps
            if clean_text.isupper():
                # Clean the POI name
                clean_text = clean_poi_name(clean_text)
                
                # Add to POIs list
                pois.append((clean_text, center_x, center_y))
    
    print(f"Found {len(pois)} potential POIs")
    return pois

# Edit POI dialog
class EditPOIDialog(wx.Dialog):
    def __init__(self, parent, poi_name, poi_x, poi_y):
        global is_editing
        is_editing = True  # Set editing flag when dialog opens
        
        wx.Dialog.__init__(self, parent, title="Edit POI", size=(300, 200))
        
        # Create a panel and sizer
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create form fields
        name_label = wx.StaticText(panel, label="POI Name:")
        self.name_ctrl = wx.TextCtrl(panel, value=poi_name)
        
        x_label = wx.StaticText(panel, label="X Position:")
        self.x_ctrl = wx.TextCtrl(panel, value=str(poi_x))
        
        y_label = wx.StaticText(panel, label="Y Position:")
        self.y_ctrl = wx.TextCtrl(panel, value=str(poi_y))
        
        # Format checkbox
        self.remove_symbols_check = wx.CheckBox(panel, label="Remove non-punctuation symbols")
        self.remove_symbols_check.SetValue(True)
        
        # Create buttons
        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        
        # Add everything to sizer
        grid = wx.FlexGridSizer(3, 2, 10, 10)
        grid.Add(name_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.name_ctrl, 1, wx.EXPAND)
        grid.Add(x_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.x_ctrl, 1, wx.EXPAND)
        grid.Add(y_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.y_ctrl, 1, wx.EXPAND)
        
        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(self.remove_symbols_check, 0, wx.ALL, 10)
        sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(sizer)
        
        # Bind the close event to reset editing flag
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        
    def OnClose(self, event):
        global is_editing
        is_editing = False  # Reset editing flag when dialog closes
        event.Skip()  # Continue with default close behavior
        
    def GetValues(self):
        global is_editing
        is_editing = False  # Reset editing flag when we get values
        
        name = self.name_ctrl.GetValue()
        
        # Apply formatting if checked
        if self.remove_symbols_check.GetValue():
            name = clean_poi_name(name)
            
        try:
            x = int(self.x_ctrl.GetValue())
            y = int(self.y_ctrl.GetValue())
            return name, x, y
        except ValueError:
            return None

# Custom drag-and-drop list control
class DraggableListCtrl(wx.ListCtrl):
    def __init__(self, parent, ID=wx.ID_ANY, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0):
        wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
        
        # Bind editing events
        self.Bind(wx.EVT_LIST_BEGIN_LABEL_EDIT, self.OnBeginEdit)
        self.Bind(wx.EVT_LIST_END_LABEL_EDIT, self.OnEndEdit)
        
        # Bind key events
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        
        # Bind drag and drop events
        self.Bind(wx.EVT_LIST_BEGIN_DRAG, self.OnBeginDrag)
        
        # Bind double click events
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)
        
        # Bind right click events
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)
        
        # For drag and drop
        self.drag_item = None
        self.drop_target = None
        
        # Parent reference for editing
        self.parent_frame = parent
        
    def OnBeginEdit(self, event):
        # Set editing flag when inline editing begins
        global is_editing
        is_editing = True
        event.Skip()
        
    def OnEndEdit(self, event):
        # Reset editing flag when inline editing ends
        global is_editing
        is_editing = False
        event.Skip()
        
    def OnKeyDown(self, event):
        key_code = event.GetKeyCode()
        
        # Check if DEL key is pressed
        if key_code == wx.WXK_DELETE:
            selected = self.GetFirstSelected()
            if selected >= 0:
                self.DeleteItem(selected)
        # Check if E key is pressed
        elif key_code == 69:  # ASCII for 'E'
            selected = self.GetFirstSelected()
            if selected >= 0:
                self.EditSelectedPOI()
        # Pass other keys
        else:
            event.Skip()
    
    def OnItemActivated(self, event):
        # Double-click handler - edit the POI
        self.EditSelectedPOI()
        
    def OnRightClick(self, event):
        # Show context menu on right click
        if not hasattr(self, "popupID1"):
            self.popupID1 = wx.NewId()
            self.popupID2 = wx.NewId()
            self.popupID3 = wx.NewId()
            
            self.Bind(wx.EVT_MENU, self.OnPopupEdit, id=self.popupID1)
            self.Bind(wx.EVT_MENU, self.OnPopupDelete, id=self.popupID2)
            self.Bind(wx.EVT_MENU, self.OnPopupMoveUp, id=self.popupID3)
        
        # Only show popup if we have an item selected
        if self.GetFirstSelected() != -1:
            # Create the popup menu
            menu = wx.Menu()
            menu.Append(self.popupID1, "Edit POI")
            menu.Append(self.popupID2, "Delete POI")
            menu.Append(self.popupID3, "Move Up")
            
            # Show the popup menu
            self.PopupMenu(menu)
            menu.Destroy()
    
    def OnPopupEdit(self, event):
        self.EditSelectedPOI()
        
    def OnPopupDelete(self, event):
        selected = self.GetFirstSelected()
        if selected >= 0:
            self.DeleteItem(selected)
            
    def OnPopupMoveUp(self, event):
        selected = self.GetFirstSelected()
        if selected > 0:
            # Get data from the selected item
            name = self.GetItemText(selected, 0)
            x_pos = self.GetItemText(selected, 1)
            y_pos = self.GetItemText(selected, 2)
            
            # Delete the item
            self.DeleteItem(selected)
            
            # Insert at the new position
            new_index = self.InsertItem(selected - 1, name)
            self.SetItem(new_index, 1, x_pos)
            self.SetItem(new_index, 2, y_pos)
            
            # Select the moved item
            self.Select(new_index)
            
    def EditSelectedPOI(self):
        selected = self.GetFirstSelected()
        if selected >= 0:
            # Get current values
            name = self.GetItemText(selected, 0)
            x_pos = self.GetItemText(selected, 1)
            y_pos = self.GetItemText(selected, 2)
            
            # Show edit dialog
            dlg = EditPOIDialog(self.parent_frame, name, x_pos, y_pos)
            if dlg.ShowModal() == wx.ID_OK:
                result = dlg.GetValues()
                if result:
                    name, x, y = result
                    # Update the item
                    self.SetItem(selected, 0, name)
                    self.SetItem(selected, 1, str(x))
                    self.SetItem(selected, 2, str(y))
            dlg.Destroy()
            
    def OnBeginDrag(self, event):
        # Get the selected item for dragging
        self.drag_item = event.GetIndex()
        
        # Start drag operation
        if self.drag_item != -1:
            # Create text data to transfer
            text_data = wx.TextDataObject()
            text_data.SetText(str(self.drag_item))
            
            # Start the drag operation
            drag_source = wx.DropSource(self)
            drag_source.SetData(text_data)
            
            # Track mouse pointer during drag
            result = drag_source.DoDragDrop(wx.Drag_AllowMove)
            
            # Handle the result
            if result == wx.DragMove:
                # The item was moved (handled in the drop event)
                pass

class POIDropTarget(wx.TextDropTarget):
    def __init__(self, list_ctrl):
        wx.TextDropTarget.__init__(self)
        self.list_ctrl = list_ctrl
        
    def OnDropText(self, x, y, data):
        # Get source item index
        source_index = int(data)
        
        # Get target item index (where we're dropping)
        target_index, flags = self.list_ctrl.HitTest((x, y))
        
        # Don't do anything if dropped on itself
        if target_index == source_index:
            return True
            
        # If dropped below the last item, set target to last position
        if target_index == -1:
            target_index = self.list_ctrl.GetItemCount() - 1
            
        # Get all data from the source item
        name = self.list_ctrl.GetItemText(source_index, 0)
        x_pos = self.list_ctrl.GetItemText(source_index, 1)
        y_pos = self.list_ctrl.GetItemText(source_index, 2)
        
        # Delete the original item
        self.list_ctrl.DeleteItem(source_index)
        
        # Insert the item at the new position
        # If we're moving an item down, we need to adjust the target index
        if target_index > source_index:
            target_index -= 1
            
        # Insert at the new position
        new_index = self.list_ctrl.InsertItem(target_index, name)
        self.list_ctrl.SetItem(new_index, 1, x_pos)
        self.list_ctrl.SetItem(new_index, 2, y_pos)
        
        # Select the moved item
        self.list_ctrl.Select(new_index)
        
        return True

class POIEditorFrame(wx.Frame):
    """Main application frame"""
    def __init__(self):
        super(POIEditorFrame, self).__init__(
            None, title="POI Editor", size=(600, 500)
        )
        
        # Create the panel
        self.panel = wx.Panel(self)
        
        # Create main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create instructions label
        instructions = wx.StaticText(self.panel, 
            label="Press F5 to capture, 'E' to edit, DEL to delete. Right-click for more options.")
        
        # Create list control for POIs
        self.poi_list = DraggableListCtrl(
            self.panel,
            style=wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_EDIT_LABELS
        )
        
        # Set up the drop target
        drop_target = POIDropTarget(self.poi_list)
        self.poi_list.SetDropTarget(drop_target)
        
        # Add columns
        self.poi_list.InsertColumn(0, "POI Name", width=250)
        self.poi_list.InsertColumn(1, "X Position", width=100)
        self.poi_list.InsertColumn(2, "Y Position", width=100)
        
        # Button sizer
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Add buttons
        self.capture_btn = wx.Button(self.panel, label="Capture (F5)")
        self.capture_btn.Bind(wx.EVT_BUTTON, self.on_capture)
        
        self.edit_btn = wx.Button(self.panel, label="Edit (E)")
        self.edit_btn.Bind(wx.EVT_BUTTON, self.on_edit)
        
        self.save_btn = wx.Button(self.panel, label="Save")
        self.save_btn.Bind(wx.EVT_BUTTON, self.on_save)
        
        self.add_btn = wx.Button(self.panel, label="Add POI")
        self.add_btn.Bind(wx.EVT_BUTTON, self.on_add)
        
        self.delete_btn = wx.Button(self.panel, label="Delete POI")
        self.delete_btn.Bind(wx.EVT_BUTTON, self.on_delete)
        
        # Add buttons to sizer
        button_sizer.Add(self.capture_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.edit_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.save_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.add_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.delete_btn, 0, wx.ALL, 5)
        
        # Add everything to main sizer
        main_sizer.Add(instructions, 0, wx.ALL, 5)
        main_sizer.Add(self.poi_list, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        
        # Set the sizer
        self.panel.SetSizer(main_sizer)
        
        # Center the frame
        self.Centre()
        
        # Initialize the list with sample data
        self.pois = []
    
    def add_poi_to_list(self, name, x, y):
        """Add a POI to the list control"""
        index = self.poi_list.InsertItem(self.poi_list.GetItemCount(), name)
        self.poi_list.SetItem(index, 1, str(x))
        self.poi_list.SetItem(index, 2, str(y))
    
    def update_list_from_pois(self):
        """Update the list control from the POIs list"""
        self.poi_list.DeleteAllItems()
        for name, x, y in self.pois:
            self.add_poi_to_list(name, x, y)
    
    def on_capture(self, event):
        """Handle capture button click"""
        global is_editing
        if is_editing:
            print("Cannot capture while editing - please finish editing first")
            return
            
        self.pois = process_screenshot()
        self.update_list_from_pois()
    
    def on_edit(self, event):
        """Handle edit button click"""
        self.poi_list.EditSelectedPOI()
    
    def on_save(self, event):
        """Handle save button click"""
        # Get all items from the list
        pois = []
        for i in range(self.poi_list.GetItemCount()):
            name = self.poi_list.GetItemText(i, 0)
            x = self.poi_list.GetItemText(i, 1)
            y = self.poi_list.GetItemText(i, 2)
            pois.append((name, x, y))
        
        # Open save dialog
        with wx.FileDialog(
            self, message="Save POI File",
            defaultDir=os.getcwd(),
            defaultFile="map_pois.txt",
            wildcard="Text files (*.txt)|*.txt",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as file_dialog:
            
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            
            # Save the file
            path = file_dialog.GetPath()
            try:
                with open(path, 'w') as f:
                    for name, x, y in pois:
                        f.write(f"{name},{x},{y}\n")
                wx.MessageBox(f"Saved {len(pois)} POIs to {path}", "Success")
            except Exception as e:
                wx.MessageBox(f"Error saving file: {e}", "Error", wx.ICON_ERROR)
    
    def on_add(self, event):
        """Add a new empty POI"""
        self.add_poi_to_list("NEW POI", "0", "0")
    
    def on_delete(self, event):
        """Delete selected POI"""
        selected = self.poi_list.GetFirstSelected()
        if selected >= 0:
            self.poi_list.DeleteItem(selected)

def main():
    app = wx.App()
    frame = POIEditorFrame()
    frame.Show()
    
    print("POI Setter Tool Ready!")
    print("Press F5 or click 'Capture' to scan the screen for POIs")
    print("Press 'E' or double-click a POI to edit it")
    print("Press DEL key to delete selected POI")
    
    # Initialize OCR in the background
    initialize_ocr()
    
    # Setup key listener in a separate thread
    def check_keys():
        # Keep track of key states
        f5_pressed = False
        e_pressed = False
        
        while True:
            # Check if F5 key is pressed
            f5_key_state = user32.GetAsyncKeyState(VK_F5)
            
            # The high bit (0x8000) is set if the key is currently pressed
            if f5_key_state & 0x8000 and not f5_pressed:
                f5_pressed = True
                # Only trigger capture if not editing
                if not is_editing:
                    # Trigger capture via wx event
                    wx.CallAfter(frame.on_capture, None)
                else:
                    print("Cannot capture while editing - please finish editing first")
            elif not (f5_key_state & 0x8000):
                f5_pressed = False
                
            # Check if E key is pressed
            e_key_state = user32.GetAsyncKeyState(VK_E)
            if e_key_state & 0x8000 and not e_pressed:
                e_pressed = True
                # Trigger edit via wx event
                wx.CallAfter(frame.on_edit, None)
            elif not (e_key_state & 0x8000):
                e_pressed = False
                
            # Small delay to prevent high CPU usage
            time.sleep(0.1)
    
    # Start key checking thread
    import threading
    key_thread = threading.Thread(target=check_keys, daemon=True)
    key_thread.start()
    
    # Start the main loop
    app.MainLoop()

if __name__ == "__main__":
    main()