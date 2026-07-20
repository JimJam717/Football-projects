"""
Control panel component for Tactical Annotator GUI
Manages GUI controls and their integration with the processing pipeline
"""

import dearpygui.dearpygui as dpg
from typing import Dict, Any, Callable, Optional
import json
import os


class ControlPanel:
    def __init__(self, config_callback: Optional[Callable] = None):
        """
        Initialize the control panel

        Args:
            config_callback: Function to call when configuration changes
        """
        self.config_callback = config_callback
        self.current_config = {}

        # Tag references for UI elements
        self.tags = {
            # File controls
            'video_path_input': 'video_path_input',
            'load_video_btn': 'load_video_btn',

            # Playback controls
            'play_button': 'play_button',
            'pause_button': 'pause_button',
            'stop_button': 'stop_button',
            'frame_slider': 'frame_slider',
            'frame_label': 'frame_label',
            'fps_label': 'fps_label',

            # Annotation toggles
            'show_rings': 'show_rings',
            'show_connections': 'show_connections',
            'show_zones': 'show_zones',
            'show_arrows': 'show_arrows',
            'show_labels': 'show_labels',

            # Parameter sliders
            'conf_slider': 'conf_slider',
            'history_slider': 'history_slider',
            'run_threshold_slider': 'run_threshold_slider',

            # Menu items
            'open_video': 'open_video_menu',
            'save_output': 'save_output_menu',
            'exit_app': 'exit_menu',
            'reset_view': 'reset_view_menu'
        }

    def create_controls(self, parent: str = None):
        """
        Create all control panel UI elements

        Args:
            parent: Parent container tag (if None, creates at root level)
        """
        parent = parent or "primary_window"

        # Only create if not already exists
        if not dpg.does_item_exist(f"{self.controls_group}_group"):
            with dpg.group(parent=parent, tag=f"{self.controls_group}_group"):
                self._create_file_controls()
                self._create_playback_controls()
                self._create_annotation_controls()
                self._create_parameter_controls()
                self._create_menu_bar()

    def _create_file_controls(self):
        """Create file-related controls"""
        with dpg.collapsing_header(label="File", parent=f"{self.controls_group}_group", default_open=True):
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Load Video",
                    tag=self.tags['load_video_btn'],
                    width=100
                )
                dpg.add_input_text(
                    hint="Video path",
                    tag=self.tags['video_path_input'],
                    readonly=True,
                    width=-1
                )

    def _create_playback_controls(self):
        """Create playback controls"""
        with dpg.collapsing_header(label="Playback", parent=f"{self.controls_group}_group", default_open=True):
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Play",
                    tag=self.tags['play_button'],
                    width=80
                )
                dpg.add_button(
                    label="Pause",
                    tag=self.tags['pause_button'],
                    width=80,
                    enabled=False
                )
                dpg.add_button(
                    label="Stop",
                    tag=self.tags['stop_button'],
                    width=80,
                    enabled=False
                )

            dpg.add_slider_int(
                label="Frame",
                tag=self.tags['frame_slider'],
                min_value=0,
                max_value=100,
                default_value=0
            )

            with dpg.group(horizontal=True):
                dpg.add_text("Frame: 0 / 0", tag=self.tags['frame_label'])
                dpg.add_text("FPS: 0", tag=self.tags['fps_label'])

    def _create_annotation_controls(self):
        """Create annotation toggle controls"""
        with dpg.collapsing_header(label="Annotations", parent=f"{self.controls_group}_group", default_open=True):
            dpg.add_checkbox(
                label="Show Rings",
                tag=self.tags['show_rings'],
                default_value=True
            )
            dpg.add_checkbox(
                label="Show Connections",
                tag=self.tags['show_connections'],
                default_value=True
            )
            dpg.add_checkbox(
                label="Show Zones",
                tag=self.tags['show_zones'],
                default_value=False
            )
            dpg.add_checkbox(
                label="Show Arrows",
                tag=self.tags['show_arrows'],
                default_value=True
            )
            dpg.add_checkbox(
                label="Show Labels",
                tag=self.tags['show_labels'],
                default_value=True
            )

    def _create_parameter_controls(self):
        """Create parameter adjustment controls"""
        with dpg.collapsing_header(label="Parameters", parent=f"{self.controls_group}_group", default_open=True):
            dpg.add_slider_float(
                label="Confidence",
                tag=self.tags['conf_slider'],
                min_value=0.1,
                max_value=1.0,
                default_value=0.35,
                format="%.2f"
            )
            dpg.add_slider_int(
                label="History Frames",
                tag=self.tags['history_slider'],
                min_value=5,
                max_value=50,
                default_value=15
            )
            dpg.add_slider_float(
                label="Run Threshold",
                tag=self.tags['run_threshold_slider'],
                min_value=1.0,
                max_value=20.0,
                default_value=8.0,
                format="%.1f"
            )

    def _create_menu_bar(self):
        """Create application menu bar"""
        if dpg.does_item_exist("main_menu_bar"):
            dpg.delete_item("main_menu_bar")

        with dpg.menu_bar(tag="main_menu_bar"):
            with dpg.menu(label="File"):
                dpg.add_menu_item(
                    label="Open Video",
                    tag=self.tags['open_video']
                )
                dpg.add_menu_item(
                    label="Save Output",
                    tag=self.tags['save_output']
                )
                dpg.add_separator()
                dpg.add_menu_item(
                    label="Exit",
                    tag=self.tags['exit_app']
                )

            with dpg.menu(label="View"):
                dpg.add_menu_item(
                    label="Reset View",
                    tag=self.tags['reset_view']
                )

    def set_file_callback(self, callback: Callable):
        """Set callback for file loading"""
        if dpg.does_item_exist(self.tags['load_video_btn']):
            dpg.set_item_callback(self.tags['load_video_btn'], callback)
        if dpg.does_item_exist(self.tags['open_video']):
            dpg.set_item_callback(self.tags['open_video'], callback)

    def set_playback_callbacks(self, play_cb: Callable, pause_cb: Callable, stop_cb: Callable):
        """Set callbacks for playback controls"""
        if dpg.does_item_exist(self.tags['play_button']):
            dpg.set_item_callback(self.tags['play_button'], play_cb)
        if dpg.does_item_exist(self.tags['pause_button']):
            dpg.set_item_callback(self.tags['pause_button'], pause_cb)
        if dpg.does_item_exist(self.tags['stop_button']):
            dpg.set_item_callback(self.tags['stop_button'], stop_cb)

    def set_frame_slider_callback(self, callback: Callable):
        """Set callback for frame slider"""
        if dpg.does_item_exist(self.tags['frame_slider']):
            dpg.set_item_callback(self.tags['frame_slider'], callback)

    def set_parameter_callbacks(self, callback: Callable):
        """Set callbacks for parameter controls"""
        param_tags = [
            self.tags['conf_slider'],
            self.tags['history_slider'],
            self.tags['run_threshold_slider']
        ]
        for tag in param_tags:
            if dpg.does_item_exist(tag):
                dpg.set_item_callback(tag, callback)

    def set_annotation_callbacks(self, callback: Callable):
        """Set callbacks for annotation toggles"""
        anno_tags = [
            self.tags['show_rings'],
            self.tags['show_connections'],
            self.tags['show_zones'],
            self.tags['show_arrows'],
            self.tags['show_labels']
        ]
        for tag in anno_tags:
            if dpg.does_item_exist(tag):
                dpg.set_item_callback(tag, callback)

    def set_menu_callbacks(self,
                          open_cb: Callable = None,
                          save_cb: Callable = None,
                          exit_cb: Callable = None,
                          reset_cb: Callable = None):
        """Set callbacks for menu items"""
        if open_cb and dpg.does_item_exist(self.tags['open_video']):
            dpg.set_item_callback(self.tags['open_video'], open_cb)
        if save_cb and dpg.does_item_exist(self.tags['save_output']):
            dpg.set_item_callback(self.tags['save_output'], save_cb)
        if exit_cb and dpg.does_item_exist(self.tags['exit_app']):
            dpg.set_item_callback(self.tags['exit_app'], exit_cb)
        if reset_cb and dpg.does_item_exist(self.tags['reset_view']):
            dpg.set_item_callback(self.tags['reset_view'], reset_cb)

    def update_video_path(self, path: str):
        """Update the video path display"""
        if dpg.does_item_exist(self.tags['video_path_input']):
            dpg.set_value(self.tags['video_path_input'], path)

    def update_frame_info(self, current: int, total: int, fps: float):
        """Update frame information display"""
        if dpg.does_item_exist(self.tags['frame_slider']):
            dpg.set_value(self.tags['frame_slider'], current)
            dpg.configure_item(self.tags['frame_slider'], max_value=max(total, 1))

        if dpg.does_item_exist(self.tags['frame_label']):
            dpg.set_value(self.tags['frame_label'], f"Frame: {current} / {total}")

        if dpg.does_item_exist(self.tags['fps_label']):
            dpg.set_value(self.tags['fps_label'], f"FPS: {fps:.1f}")

    def set_playback_state(self, is_playing: bool, is_paused: bool = False):
        """Update playback button states"""
        if dpg.does_item_exist(self.tags['play_button']):
            dpg.set_item_enabled(self.tags['play_button'], not is_playing)
        if dpg.does_item_exist(self.tags['pause_button']):
            dpg.set_item_enabled(self.tags['pause_button'], is_playing)
            dpg.set_item_label(
                self.tags['pause_button'],
                "Resume" if is_paused else "Pause"
            )
        if dpg.does_item_exist(self.tags['stop_button']):
            dpg.set_item_enabled(self.tags['stop_button'], is_playing)

    def get_current_config(self) -> Dict[str, Any]:
        """Get current configuration from GUI controls"""
        config = {}

        # Get parameter values
        if dpg.does_item_exist(self.tags['conf_slider']):
            config['confidence'] = dpg.get_value(self.tags['conf_slider'])
        if dpg.does_item_exist(self.tags['history_slider']):
            config['history_frames'] = dpg.get_value(self.tags['history_slider'])
        if dpg.does_item_exist(self.tags['run_threshold_slider']):
            config['run_threshold'] = dpg.get_value(self.tags['run_threshold_slider'])

        # Get annotation states
        if dpg.does_item_exist(self.tags['show_rings']):
            config['show_rings'] = dpg.get_value(self.tags['show_rings'])
        if dpg.does_item_exist(self.tags['show_connections']):
            config['show_connections'] = dpg.get_value(self.tags['show_connections'])
        if dpg.does_item_exist(self.tags['show_zones']):
            config['show_zones'] = dpg.get_value(self.tags['show_zones'])
        if dpg.does_item_exist(self.tags['show_arrows']):
            config['show_movement_arrows'] = dpg.get_value(self.tags['show_arrows'])
        if dpg.does_item_exist(self.tags['show_labels']):
            config['show_labels'] = dpg.get_value(self.tags['show_labels'])

        self.current_config = config

        # Call callback if provided
        if self.config_callback:
            self.config_callback(config)

        return config

    def apply_config(self, config: Dict[str, Any]):
        """Apply configuration to GUI controls"""
        self.current_config = config.copy()

        # Apply parameter values
        if 'confidence' in config and dpg.does_item_exist(self.tags['conf_slider']):
            dpg.set_value(self.tags['conf_slider'], config['confidence'])
        if 'history_frames' in config and dpg.does_item_exist(self.tags['history_slider']):
            dpg.set_value(self.tags['history_slider'], config['history_frames'])
        if 'run_threshold' in config and dpg.does_item_exist(self.tags['run_threshold_slider']):
            dpg.set_value(self.tags['run_threshold_slider'], config['run_threshold'])

        # Apply annotation states
        if 'show_rings' in config and dpg.does_item_exist(self.tags['show_rings']):
            dpg.set_value(self.tags['show_rings'], config['show_rings'])
        if 'show_connections' in config and dpg.does_item_exist(self.tags['show_connections']):
            dpg.set_value(self.tags['show_connections'], config['show_connections'])
        if 'show_zones' in config and dpg.does_item_exist(self.tags['show_zones']):
            dpg.set_value(self.tags['show_zones'], config['show_zones'])
        if 'show_movement_arrows' in config and dpg.does_item_exist(self.tags['show_arrows']):
            dpg.set_value(self.tags['show_arrows'], config['show_movement_arrows'])
        if 'show_labels' in config and dpg.does_item_exist(self.tags['show_labels']):
            dpg.set_value(self.tags['show_labels'], config['show_labels'])

    def cleanup(self):
        """Clean up resources"""
        # In a full implementation, we might want to remove UI elements
        # For now, we just clear references
        self.current_config = {}