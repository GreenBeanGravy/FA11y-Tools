# main.py
import cv2
import numpy as np
import os
import time
from mss import mss
import tkinter as tk
from tkinter import simpledialog
from pynput import keyboard
import threading
import accessible_output2.outputs.auto
from image_cache import ImageCache

# Constants
BASE_SLOT_COORDS = [
    (1514, 931, 1577, 975),  # Slot 1
    (1595, 931, 1658, 975),  # Slot 2
    (1677, 931, 1740, 975),  # Slot 3
    (1759, 931, 1822, 975),  # Slot 4
    (1840, 931, 1903, 975)   # Slot 5
]
SLOT_COORDS = (1502, 931, 1565, 975)  # left, top, right, bottom for single slot capture
IMAGES_FOLDER = "cache"  # Folder for reference images
DISPLAY_SIZE = (250, 250)  # Size for display images
CONFIDENCE_THRESHOLD = 0.5  # Minimum confidence to consider a match valid
FPS = 10

# Arrow key constants for OpenCV
KEY_LEFT = 81  # Left arrow key code
KEY_RIGHT = 83  # Right arrow key code
KEY_UP = 82  # Up arrow key code 
KEY_DOWN = 84  # Down arrow key code

# Global variables
x_offset = 0.0
y_offset = 0.0
running = True
monitoring = False
last_detected_items = [None, None, None, None, None]
speaker = accessible_output2.outputs.auto.Auto()
image_cache = ImageCache()

def apply_offset(coords):
    """Apply the current offset to coordinates"""
    return [
        (
            coord[0] + x_offset,
            coord[1] + y_offset,
            coord[2] + x_offset,
            coord[3] + y_offset
        )
        for coord in coords
    ]

def print_coordinates():
    """Print the current hotbar coordinates with offsets applied"""
    slot_coords = apply_offset(BASE_SLOT_COORDS)
    print("\nCurrent Hotbar Coordinates:")
    for i, coord in enumerate(slot_coords, 1):
        print(f"Slot {i}: Top Left ({coord[0]:.2f}, {coord[1]:.2f}), Bottom Right ({coord[2]:.2f}, {coord[3]:.2f})")

def load_reference_images(folder):
    """Load all reference images from the folder"""
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
        print(f"Created images folder: {folder}")
        
    images = {}
    for filename in os.listdir(folder):
        if filename.endswith((".png", ".jpg", ".jpeg")):
            img = cv2.imread(os.path.join(folder, filename))
            if img is not None:
                img = cv2.resize(img, (int(BASE_SLOT_COORDS[0][2] - BASE_SLOT_COORDS[0][0]), 
                                      int(BASE_SLOT_COORDS[0][3] - BASE_SLOT_COORDS[0][1])))
                name = os.path.splitext(filename)[0]
                images[name] = img
    return images

def match_template(image, template):
    """Match a slot image against a template image"""
    result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val

def capture_and_save_image():
    """Capture a single slot and prompt for name"""
    # Capture the screenshot
    with mss() as sct:
        screenshot = np.array(sct.grab(SLOT_COORDS))
    
    # Convert the image from BGRA to RGB
    screenshot_rgb = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2RGB)
    
    # Create Tkinter root window
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    # Prompt for image name
    image_name = simpledialog.askstring("Image Name", "Enter a name for the captured image:")
    
    if image_name:
        # Ensure the images folder exists
        os.makedirs(IMAGES_FOLDER, exist_ok=True)
        
        # Save the image
        file_path = os.path.join(IMAGES_FOLDER, f"{image_name}.png")
        cv2.imwrite(file_path, cv2.cvtColor(screenshot_rgb, cv2.COLOR_RGB2BGR))
        speaker.speak(f"Image saved as {image_name}")
        print(f"Image saved as {file_path}")
        
        # Update the image cache
        image_cache.cache_images(IMAGES_FOLDER)
    else:
        speaker.speak("Image capture cancelled")
        print("Image capture cancelled")

def on_press(key):
    """Handle keyboard shortcuts"""
    global monitoring, running
    
    if key == keyboard.Key.f12:
        # F12 - Capture reference image
        capture_and_save_image()
    elif key == keyboard.Key.f10:
        # F10 - Toggle monitoring
        monitoring = not monitoring
        if monitoring:
            speaker.speak("Hotbar monitoring started")
            print("Hotbar monitoring started")
        else:
            speaker.speak("Hotbar monitoring paused")
            print("Hotbar monitoring paused")
    elif key == keyboard.Key.f9:
        # F9 - Exit program
        speaker.speak("Exiting program")
        print("Exiting program")
        running = False
        return False  # Stop the listener

def monitor_hotbar():
    """Monitor the hotbar slots and detect changes"""
    global running, last_detected_items, x_offset, y_offset
    
    sct = mss()
    reference_images = load_reference_images(IMAGES_FOLDER)
    
    # Create window for visualization
    cv2.namedWindow("Hotbar Detection")
    
    print("Loaded", len(reference_images), "reference images")
    if not reference_images:
        print(f"No reference images found in {IMAGES_FOLDER} folder. Use F12 to capture some.")
    
    while running:
        if not monitoring:
            time.sleep(0.1)
            continue
            
        start_time = time.time()

        # Apply offsets to slot coordinates
        slot_coords = apply_offset(BASE_SLOT_COORDS)

        # Capture all slots
        screenshots = [np.array(sct.grab(tuple(map(int, coord)))) for coord in slot_coords]
        screenshots_rgb = [cv2.cvtColor(screenshot, cv2.COLOR_RGBA2RGB) for screenshot in screenshots]

        # Process each slot
        current_detected = []
        for idx, screenshot_rgb in enumerate(screenshots_rgb):
            best_match = None
            best_score = -1
            
            for name, ref_img in reference_images.items():
                score = match_template(screenshot_rgb, ref_img)
                if score > best_score:
                    best_score = score
                    best_match = name
                    
            # Only consider it a match if above threshold
            if best_score < CONFIDENCE_THRESHOLD:
                best_match = None
                
            current_detected.append(best_match)
            
            # Announce changes via speech output
            if current_detected[idx] != last_detected_items[idx]:
                slot_num = idx + 1
                if current_detected[idx]:
                    speaker.speak(f"Slot {slot_num}: {current_detected[idx]}")
                else:
                    speaker.speak(f"Slot {slot_num}: Empty")
        
        # Update the last detected items
        last_detected_items = current_detected.copy()

        # Create display image
        display_images = [cv2.resize(img, DISPLAY_SIZE) for img in screenshots_rgb]
        top_row = np.hstack(display_images[:3])
        bottom_row = np.hstack([display_images[3], display_images[4], np.zeros_like(display_images[0])])
        display = np.vstack([top_row, bottom_row])

        # Add detection results to the image
        for idx, item in enumerate(current_detected):
            x_offset_display = (idx % 3) * DISPLAY_SIZE[0]
            y_offset_display = (idx // 3) * DISPLAY_SIZE[1]
            
            text = item if item else "Empty"
            color = (0, 255, 0) if item else (0, 0, 255)
            
            cv2.putText(display, f"Slot {idx+1}: {text}", 
                        (x_offset_display + 5, y_offset_display + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        # Display threshold and current offsets
        cv2.putText(display, f"Threshold: {CONFIDENCE_THRESHOLD}", 
                    (5, display.shape[0] - 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(display, f"X/Y Offset: {x_offset:.1f}/{y_offset:.1f}", 
                    (5, display.shape[0] - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(display, "F10: Toggle | F12: Capture | F9: Exit | Arrows: Adjust", 
                    (5, display.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow("Hotbar Detection", display)

        # Handle key presses for adjustment
        key = cv2.waitKey(1) & 0xFF
        
        # Check for arrow keys (the exact key codes can vary by platform)
        # Try the standard key codes first
        if key == KEY_LEFT or key == 81 or key == 2424832:
            # Left arrow - move hotbar left
            x_offset -= 0.5
            print_coordinates()
        elif key == KEY_RIGHT or key == 83 or key == 2555904:
            # Right arrow - move hotbar right
            x_offset += 0.5
            print_coordinates()
        elif key == KEY_UP or key == 82 or key == 2490368:
            # Up arrow - move hotbar up
            y_offset -= 0.5
            print_coordinates()
        elif key == KEY_DOWN or key == 84 or key == 2621440:
            # Down arrow - move hotbar down
            y_offset += 0.5
            print_coordinates()
        elif key == ord('r'):
            # Reload reference images
            reference_images = load_reference_images(IMAGES_FOLDER)
            print("Reloaded", len(reference_images), "reference images")

        # Sleep to maintain frame rate
        time.sleep(max(1./FPS - (time.time() - start_time), 0))

    cv2.destroyAllWindows()

def main():
    global running
    
    # Initialize the image cache
    success, message = image_cache.cache_images(IMAGES_FOLDER)
    print(message)
    
    # Start monitoring thread
    monitor_thread = threading.Thread(target=monitor_hotbar)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    print("Hotbar Monitor Ready!")
    print("F10: Toggle monitoring on/off")
    print("F12: Capture a new reference image")
    print("F9: Exit program")
    print("Arrow keys: Adjust hotbar position")
    print("R: Reload reference images")
    
    # Start listening for key presses
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()
    
    # Ensure clean exit
    running = False
    monitor_thread.join(timeout=1.0)
    print("Program terminated")

if __name__ == "__main__":
    main()