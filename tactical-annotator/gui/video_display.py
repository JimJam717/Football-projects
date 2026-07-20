"""
Video display component for Tactical Annotator GUI
Handles texture management and video frame display using Dear PyGui
"""

import numpy as np
import cv2
import dearpygui.dearpygui as dpg
from typing import Optional, Tuple


class VideoDisplay:
    def __init__(self, width: int = 0, height: int = 0):
        self.width = width
        self.height = height
        self.texture_tag = "video_texture"
        self.image_tag = "video_image"
        self.texture_data = None
        self.is_initialized = False

    def initialize(self, width: int, height: int):
        """Initialize the video display with given dimensions"""
        self.width = width
        self.height = height

        # Create texture data (RGBA float32 for Dear PyGui)
        self.texture_data = np.zeros((height, width, 4), dtype=np.float32)

        # Register texture if not exists, otherwise update
        if dpg.does_item_exist(self.texture_tag):
            # Update existing texture
            self._update_texture_registry()
        else:
            # Create new texture
            with dpg.texture_registry():
                dpg.add_raw_texture(
                    width, height, self.texture_data,
                    format=dpg.mvFormat_Float_rgba,
                    tag=self.texture_tag
                )

        # Add or update image item
        if dpg.does_item_exist(self.image_tag):
            # Just reconfigure if needed
            pass
        else:
            # In a real implementation, this would be added to a parent container
            # For now, we assume the caller will manage the UI layout
            pass

        self.is_initialized = True

    def update_frame(self, frame: np.ndarray):
        """
        Update the displayed frame

        Args:
            frame: OpenCV image (BGR format) to display
        """
        if not self.is_initialized or frame is None:
            return

        # Convert BGR to RGBA
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            # BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Add alpha channel (fully opaque)
            rgba_frame = np.concatenate([
                rgb_frame,
                np.full((rgb_frame.shape[0], rgb_frame.shape[1], 1), 255, dtype=np.uint8)
            ], axis=2)
        elif len(frame.shape) == 3 and frame.shape[2] == 4:
            # Already BGRA, convert to RGBA
            rgba_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGBA)
        else:
            # Grayscale - convert to RGBA
            gray_to_rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
            rgba_frame = np.concatenate([
                gray_to_rgb,
                np.full((gray_to_rgb.shape[0], gray_to_rgb.shape[1], 1), 255, dtype=np.uint8)
            ], axis=2)

        # Normalize to 0-1 float for Dear PyGui
        normalized_frame = rgba_frame.astype(np.float32) / 255.0

        # Update texture data
        self.texture_data[:] = normalized_frame

        # Update the texture in Dear PyGui
        if dpg.does_item_exist(self.texture_tag):
            dpg.set_value(self.texture_tag, self.texture_data.flatten())

    def _update_texture_registry(self):
        """Update the texture registry with new dimensions"""
        # Delete old texture if exists
        if dpg.does_item_exist(self.texture_tag):
            dpg.delete_item(self.texture_tag)

        # Create new texture
        with dpg.texture_registry():
            dpg.add_raw_texture(
                self.width, self.height, self.texture_data,
                format=dpg.mvFormat_Float_rgba,
                tag=self.texture_tag
            )

    def get_texture_tag(self) -> str:
        """Get the texture tag for binding"""
        return self.texture_tag

    def get_image_tag(self) -> str:
        """Get the image tag for display"""
        return self.image_tag

    def cleanup(self):
        """Clean up resources"""
        if dpg.does_item_exist(self.texture_tag):
            dpg.delete_item(self.texture_tag)
        if dpg.does_item_exist(self.image_tag):
            dpg.delete_item(self.image_tag)
        self.is_initialized = False