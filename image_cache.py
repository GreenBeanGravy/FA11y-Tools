# image_cache.py
import os
import pickle
import zlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Tuple, Optional
import time

class ImageCache:
    def __init__(self, compression_level: int = 6):
        """
        Initialize the image cache with configurable compression.
        
        Args:
            compression_level (int): zlib compression level (0-9), higher = smaller size but slower
        """
        self.compression_level = compression_level
        self.cache: Dict[str, dict] = {}
        self.cache_file = "image_cache.pkl"
        
    def _process_image(self, image_path: Path) -> Tuple[str, dict]:
        """Process a single image file."""
        try:
            # Read and compress in chunks for memory efficiency
            with open(image_path, 'rb') as f:
                data = f.read()
            
            compressed = zlib.compress(data, self.compression_level)
            
            return str(image_path.name), {
                'data': compressed,
                'size': len(data),
                'modified': os.path.getmtime(image_path),
                'compressed_size': len(compressed)
            }
        except Exception as e:
            print(f"Warning: Failed to process {image_path}: {e}")
            return None

    def cache_images(self, image_dir: str = "images", cache_file: str = None, 
                    max_workers: int = None) -> Tuple[bool, str]:
        """
        Cache all PNG images from a directory using parallel processing.
        
        Args:
            image_dir (str): Directory containing PNG images
            cache_file (str): Output cache file name (default is instance cache_file)
            max_workers (int): Maximum number of thread workers (None = CPU count)
        
        Returns:
            tuple: (Success status, Message with timing and compression stats)
        """
        if cache_file:
            self.cache_file = cache_file
            
        start_time = time.time()
        
        try:
            if not os.path.exists(image_dir):
                os.makedirs(image_dir, exist_ok=True)
                return True, f"Created empty directory '{image_dir}'"

            # Get all PNG files
            image_paths = list(Path(image_dir).glob("*.png"))
            
            if not image_paths:
                return True, "No PNG files found in directory"

            # Process images in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = executor.map(self._process_image, image_paths)
            
            # Filter out None results and update cache
            total_original = 0
            total_compressed = 0
            
            for result in results:
                if result:
                    name, data = result
                    self.cache[name] = data
                    total_original += data['size']
                    total_compressed += data['compressed_size']

            # Save cache using pickle (faster than JSON for binary data)
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f, protocol=pickle.HIGHEST_PROTOCOL)

            elapsed = time.time() - start_time
            compression_ratio = (total_compressed / total_original) * 100 if total_original else 0
            
            return True, (
                f"Cached {len(self.cache)} images in {elapsed:.2f} seconds\n"
                f"Original size: {total_original/1024/1024:.2f}MB\n"
                f"Compressed size: {total_compressed/1024/1024:.2f}MB\n"
                f"Compression ratio: {compression_ratio:.1f}%"
            )

        except Exception as e:
            return False, f"Error: {str(e)}"

    def load_cached_image(self, image_name: str) -> Optional[bytes]:
        """
        Load a specific image from the cache file.
        
        Args:
            image_name (str): Name of the image file
        
        Returns:
            bytes: Decompressed image data if found, None otherwise
        """
        try:
            if not self.cache:  # Load cache if not already loaded
                if os.path.exists(self.cache_file):
                    with open(self.cache_file, 'rb') as f:
                        self.cache = pickle.load(f)
            
            if image_name in self.cache:
                return zlib.decompress(self.cache[image_name]['data'])
            return None
            
        except Exception as e:
            print(f"Error loading from cache: {str(e)}")
            return None
    
    def clear_cache(self):
        """Clear the current cache."""
        self.cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)