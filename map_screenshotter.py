import ctypes
from PIL import ImageGrab
import wx
import os
import sys
import time

# Define the area for the screenshot
x1, y1 = 524, 84
x2, y2 = 1390, 1010

# Virtual key codes
VK_C = 0x43
VK_CONTROL = 0x11

# Get reference to user32.dll for keyboard input
user32 = ctypes.windll.user32

def take_screenshot():
    print("Capturing screenshot...")
    try:
        # Take a screenshot of the specified area
        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        
        # Initialize wx application
        app = wx.App(None)
        
        # Get the current directory to use as default
        default_dir = os.getcwd()
        
        print("Opening save dialog...")
        # Create and show the file dialog
        with wx.FileDialog(
            None, 
            message="Save Screenshot As",
            defaultDir=default_dir,
            defaultFile="map.png",
            wildcard="PNG files (*.png)|*.png|All files (*.*)|*.*",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as file_dialog:
            
            # If user clicked "OK"
            if file_dialog.ShowModal() == wx.ID_OK:
                file_path = file_dialog.GetPath()
                screenshot.save(file_path)
                print(f"Screenshot saved as {file_path}")
            else:
                print("Screenshot save canceled")
        
        # Clean up the wx app
        app.Destroy()
    except Exception as e:
        print(f"An error occurred: {e}")

def main():
    print("Fortnite Map Screenshot Tool Ready!")
    print("Press 'C' to capture screenshot of the Fortnite map")
    print("Press Ctrl+C to exit the program")
    print("Waiting...")
    
    # Keep track of key states to detect when key is first pressed
    c_pressed = False
    
    try:
        while True:
            # Check if C key is pressed
            c_key_state = user32.GetAsyncKeyState(VK_C)
            
            # The high bit (0x8000) is set if the key is currently pressed
            if c_key_state & 0x8000 and not c_pressed:
                c_pressed = True
                take_screenshot()
            elif not (c_key_state & 0x8000):
                c_pressed = False
                
            # Check if Ctrl+C is pressed
            if user32.GetAsyncKeyState(VK_CONTROL) & 0x8000 and user32.GetAsyncKeyState(ord('C')) & 0x8000:
                print("\nCtrl+C detected - Exiting program...")
                sys.exit(0)
                
            # Small delay to prevent high CPU usage
            time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\nExiting program...")
        sys.exit(0)

if __name__ == "__main__":
    main()