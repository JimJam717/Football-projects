"""
Main GUI application for Tactical Annotator
Provides a graphical interface for the tactical video annotation pipeline
"""

import dearpygui.dearpygui as dpg
import threading
import time
import os
import cv2
import numpy as np
from pathlib import Path

# Import existing modules
import sys
sys.path.append(str(Path(__file__).parent.parent))

from main import load_config, run_pipeline
from modules.detector import PlayerDetector
from modules.tracker import PlayerTracker
from modules.classifier import TeamClassifier
from modules.analyzer import MovementAnalyzer
from modules.renderer import (
    draw_glowing_ring,
    draw_connecting_line,
    draw_hatched_zone,
    draw_dashed_arrow,
    draw_player_label
)

class TacticalAnnotatorGUI:
    def __init__(self):
        self.is_playing = False
        self.is_paused = False
        self.current_frame = 0
        self.total_frames = 0
        self.fps = 30
        self.video_path = ""
        self.output_path = ""
        self.config = None
        self.file_dialog_tag = "file_dialog"
        self.classifier_fitted = False
        self._team_cache = {}
        self.video_window_tag = "video_window"

        # Processing components
        self.detector = None
        self.tracker = None
        self.classifier = None
        self.analyzer = None

        # Texture for video display
        self.texture_texture = None
        self.texture_width = 0
        self.texture_height = 0

        # UI element tags
        self.video_texture_tag = "video_texture"
        self.video_image_tag = "video_image"
        self.play_button_tag = "play_button"
        self.pause_button_tag = "pause_button"
        self.stop_button_tag = "stop_button"
        self.frame_slider_tag = "frame_slider"
        self.fps_label_tag = "fps_label"
        self.frame_label_tag = "frame_label"

        # Configuration controls
        self.conf_slider_tag = "conf_slider"
        self.history_slider_tag = "history_slider"
        self.run_threshold_slider_tag = "run_threshold_slider"

        # Toggle buttons
        self.show_rings_tag = "show_rings"
        self.show_connections_tag = "show_connections"
        self.show_zones_tag = "show_zones"
        self.show_arrows_tag = "show_arrows"
        self.show_labels_tag = "show_labels"

    def start_dearpygui(self):
        """Initialize and start the Dear PyGui context"""
        dpg.create_context()
        dpg.create_viewport(title='Tactical Annotator', width=1200, height=800)

        # Setup fonts
        with dpg.font_registry():
            with dpg.font("C:/Windows/Fonts/arial.ttf", 18) as default_font:
                dpg.bind_font(default_font)

        # Create UI
        self._create_ui()

        # Setup viewport
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("primary_window", True)

        # Start render loop
        while dpg.is_dearpygui_running():
            self._update_ui()
            dpg.render_dearpygui_frame()

        dpg.destroy_context()

    def _create_ui(self):
        """Create the main user interface"""
        with dpg.window(label="Tactical Annotator", tag="primary_window"):
            # Menu bar
            with dpg.menu_bar():
                with dpg.menu(label="File"):
                    dpg.add_menu_item(label="Open Video", callback=self._callback_open_video)
                    dpg.add_menu_item(label="Save Output", callback=self._callback_save_output)
                    dpg.add_separator()
                    dpg.add_menu_item(label="Exit", callback=lambda: dpg.stop_dearpygui())

                with dpg.menu(label="View"):
                    dpg.add_menu_item(label="Reset View", callback=self._callback_reset_view)

            # Main content area
            with dpg.group(horizontal=True):
                # Video display area
                with dpg.child_window(width=800, height=600, border=True, tag=self.video_window_tag):
                    # This will contain the video texture
                    dpg.add_text("No video loaded", pos=(20, 20), tag="video_placeholder")

                # Control panel
                with dpg.child_window(width=350, height=600, border=True):
                    dpg.add_text("Controls")
                    dpg.add_separator()

                    # File controls
                    dpg.add_button(label="Load Video", width=-1, callback=self._callback_open_video)
                    dpg.add_input_text(hint="Video path", readonly=True, tag="video_path_input", width=-1)

                    dpg.add_separator()

                    # Playback controls
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Play", width=80, tag=self.play_button_tag,
                                     callback=self._callback_play)
                        dpg.add_button(label="Pause", width=80, tag=self.pause_button_tag,
                                     callback=self._callback_pause)
                        dpg.add_button(label="Stop", width=80, tag=self.stop_button_tag,
                                     callback=self._callback_stop)

                    # Frame slider
                    dpg.add_slider_int(label="Frame", min_value=0, max_value=100,
                                     default_value=0, tag=self.frame_slider_tag,
                                     callback=self._callback_frame_slider)

                    # Info labels
                    dpg.add_text("Frame: 0 / 0", tag=self.frame_label_tag)
                    dpg.add_text("FPS: 0", tag=self.fps_label_tag)

                    dpg.add_separator()
                    dpg.add_text("Annotation Options")

                    # Toggle buttons for annotations
                    dpg.add_checkbox(label="Show Rings", tag=self.show_rings_tag,
                                   default_value=True, callback=self._callback_toggle_annotation)
                    dpg.add_checkbox(label="Show Connections", tag=self.show_connections_tag,
                                   default_value=True, callback=self._callback_toggle_annotation)
                    dpg.add_checkbox(label="Show Zones", tag=self.show_zones_tag,
                                   default_value=False, callback=self._callback_toggle_annotation)
                    dpg.add_checkbox(label="Show Arrows", tag=self.show_arrows_tag,
                                   default_value=True, callback=self._callback_toggle_annotation)
                    dpg.add_checkbox(label="Show Labels", tag=self.show_labels_tag,
                                   default_value=True, callback=self._callback_toggle_annotation)

                    dpg.add_separator()
                    dpg.add_text("Parameters")

                    # Configuration sliders
                    dpg.add_slider_float(label="Confidence", min_value=0.1, max_value=1.0,
                                       default_value=0.35, tag=self.conf_slider_tag,
                                       format="%.2f", callback=self._callback_param_change)
                    dpg.add_slider_int(label="History Frames", min_value=5, max_value=50,
                                     default_value=15, tag=self.history_slider_tag,
                                     callback=self._callback_param_change)
                    dpg.add_slider_float(label="Run Threshold", min_value=1.0, max_value=20.0,
                                       default_value=8.0, tag=self.run_threshold_slider_tag,
                                       format="%.1f", callback=self._callback_param_change)
        with dpg.file_dialog(directory_selector=False, show=False, callback=self._callback_file_selector,
                                 width=700, height=400, tag=self.file_dialog_tag):
                dpg.add_file_extension('.mp4')
                dpg.add_file_extension('.avi')
                dpg.add_file_extension('.mov')
                dpg.add_file_extension('.*')

    def _callback_open_video(self, sender, app_data):
        """Handle open video file dialog"""
        if isinstance(app_data, str):
            # Single file selection
            file_path = app_data
        elif app_data is not None and 'selections' in app_data:
            # Multiple file selection (take first)
            file_path = list(app_data['selections'].values())[0]
        else:
            # No valid data from caller - show the file picker instead
            dpg.show_item(self.file_dialog_tag)
            return

        self.video_path = file_path
        dpg.set_value("video_path_input", file_path)
        self._load_video_info()

    def _callback_file_selector(self, sender, app_data):
        """Handle file selection from the file dialog"""
        if isinstance(app_data, str):
            # Single file selection
            file_path = app_data
        elif app_data is not None and 'selections' in app_data:
            # Multiple file selection (take first)
            file_path = list(app_data['selections'].values())[0]
        else:
            return

        self.video_path = file_path
        dpg.set_value("video_path_input", file_path)
        dpg.hide_item(self.file_dialog_tag)  # hide dialog after selection
        self._load_video_info()

    def _load_video_info(self):
        """Load video information and prepare for playback"""
        if not self.video_path or not os.path.exists(self.video_path):
            return

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            dpg.set_value("video_placeholder", "Error: Could not open video")
            return

        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = cap.get(cv2.CAP_PROP_FPS)

        cap.release()

        # Load configuration
        self.config = load_config('config.yaml')

        # Update config from GUI controls
        self._update_config_from_gui()

        # Initialize processing components
        self._init_processing_components()

        # Get output size from config
        out_w, out_h = self.config['output_size']

        # Prepare texture for display (using output size)
        self._prepare_texture(out_w, out_h)

        # Update UI
        dpg.set_value(self.frame_label_tag, f"Frame: 0 / {self.total_frames}")
        dpg.set_value(self.fps_label_tag, f"FPS: {self.fps:.1f}")
        dpg.configure_item(self.frame_slider_tag, max_value=self.total_frames)
        dpg.set_value(self.frame_slider_tag, 0)

        # Clear placeholder
        if dpg.does_item_exist("video_placeholder"):
            dpg.delete_item("video_placeholder")

        # Show first frame
        self._show_frame(0)

    def _prepare_texture(self, width, height):
        """Prepare Dear PyGui texture for video display"""
        self.texture_width = width
        self.texture_height = height

        # Create texture buffer (RGBA format for Dear PyGui)
        texture_data = np.zeros((height, width, 4), dtype=np.float32)

        # Handle texture: reuse if same size, otherwise recreate
        texture_exists = dpg.does_item_exist(self.video_texture_tag)
        if texture_exists:
            # Get existing texture size (we don't have a direct way, so we'll assume it's the same if we are calling with the same width/height)
            # For simplicity, we'll recreate if the size might have changed (but we are passing fixed output size)
            # We'll just update the data if the texture exists.
            pass  # We'll update the data below
        else:
            # Texture doesn't exist, create it
            with dpg.texture_registry():
                self.texture_texture = dpg.add_raw_texture(
                    width, height, texture_data,
                    format=dpg.mvFormat_Float_rgba,
                    tag=self.video_texture_tag
                )

        # Update the texture data (whether we just created it or it already existed)
        dpg.set_value(self.video_texture_tag, texture_data.flatten())

        # Handle image: only create if it doesn't exist
        if not dpg.does_item_exist(self.video_image_tag):
            dpg.add_image(self.video_texture_tag, tag=self.video_image_tag, parent=self.video_window_tag)

    def _init_processing_components(self):
        """Initialize the processing pipeline components"""
        if not self.config:
            return

        try:
            self.detector = PlayerDetector(
                self.config['model_path'],
                self.config['confidence']
            )

            self.tracker = PlayerTracker(
                lost_track_buffer=self.config['lost_track_buffer'],
                min_matching_threshold=self.config['min_matching_threshold']
            )

            self.classifier = TeamClassifier(n_clusters=3)
            # Reset classifier state for new video
            self.classifier_fitted = False
            self._team_cache = {}

            self.analyzer = MovementAnalyzer(
                history_len=self.config['history_frames'],
                run_threshold=self.config['run_threshold']
            )

        except Exception as e:
            print(f"Error initializing components: {e}")
            # Show error in UI
            with dpg.window(label="Error", modal=True, show=True, tag="error_modal"):
                dpg.add_text(f"Failed to initialize components: {str(e)}")
                dpg.add_button(label="OK", width=75,
                             callback=lambda: dpg.delete_item("error_modal"))

    def _update_config_from_gui(self):
        """Update configuration values from GUI controls"""
        if not self.config:
            return

        self.config['confidence'] = dpg.get_value(self.conf_slider_tag)
        self.config['history_frames'] = dpg.get_value(self.history_slider_tag)
        self.config['run_threshold'] = dpg.get_value(self.run_threshold_slider_tag)
        self.config['show_rings'] = dpg.get_value(self.show_rings_tag)
        self.config['show_connections'] = dpg.get_value(self.show_connections_tag)
        self.config['show_zones'] = dpg.get_value(self.show_zones_tag)
        self.config['show_movement_arrows'] = dpg.get_value(self.show_arrows_tag)
        self.config['show_labels'] = dpg.get_value(self.show_labels_tag)

    def _callback_play(self, sender, app_data):
        """Handle play button press"""
        if not self.video_path:
            return

        self.is_playing = True
        self.is_paused = False

        # Start processing thread
        self.process_thread = threading.Thread(target=self._process_video_loop)
        self.process_thread.daemon = True
        self.process_thread.start()

        # Update button states
        dpg.configure_item(self.play_button_tag, enabled=False)
        dpg.configure_item(self.pause_button_tag, enabled=True)
        dpg.configure_item(self.stop_button_tag, enabled=True)

    def _callback_pause(self, sender, app_data):
        """Handle pause button press"""
        self.is_paused = not self.is_paused
        if self.is_paused:
            dpg.configure_item(self.pause_button_tag, label="Resume")
        else:
            dpg.configure_item(self.pause_button_tag, label="Pause")

    def _callback_stop(self, sender, app_data):
        """Handle stop button press"""
        self.is_playing = False
        self.is_paused = False

        # Update button states
        dpg.configure_item(self.play_button_tag, enabled=True)
        dpg.configure_item(self.pause_button_tag, enabled=False, label="Pause")
        dpg.configure_item(self.stop_button_tag, enabled=False)

        # Reset to first frame
        self.current_frame = 0
        dpg.set_value(self.frame_slider_tag, 0)
        self._show_frame(0)

    def _callback_frame_slider(self, sender, app_data):
        """Handle frame slider movement"""
        if not self.is_playing:  # Only allow seeking when not playing
            frame_num = int(app_data)
            self.current_frame = frame_num
            self._show_frame(frame_num)
            dpg.set_value(self.frame_label_tag, f"Frame: {frame_num} / {self.total_frames}")

    def _callback_param_change(self, sender, app_data):
        """Handle parameter slider changes"""
        self._update_config_from_gui()
        # If we have a paused video, update the current frame display
        if not self.is_playing and self.video_path:
            self._show_frame(self.current_frame)

    def _callback_toggle_annotation(self, sender, app_data):
        """Handle annotation toggle changes"""
        self._update_config_from_gui()
        # If we have a paused video, update the current frame display
        if not self.is_playing and self.video_path:
            self._show_frame(self.current_frame)

    def _process_video_loop(self):
        """Main video processing loop running in separate thread"""
        if not self.video_path or not os.path.exists(self.video_path):
            return

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            return

        # Set starting position
        cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)

        frame_time = 1.0 / self.fps if self.fps > 0 else 1.0 / 30.0

        while self.is_playing and cap.isOpened():
            if self.is_paused:
                time.sleep(0.1)
                continue

            start_time = time.time()

            ret, frame = cap.read()
            if not ret:
                # End of video
                self.is_playing = False
                break

            # Process frame
            processed_frame = self._process_frame(frame, int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1)

            # Update texture for display
            self._update_texture(processed_frame)

            # Update frame counter
            self.current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            dpg.set_value(self.frame_slider_tag, self.current_frame)
            dpg.set_value(self.frame_label_tag,
                         f"Frame: {self.current_frame} / {self.total_frames}")

            # Calculate and display FPS
            elapsed = time.time() - start_time
            if elapsed > 0:
                current_fps = 1.0 / elapsed
                dpg.set_value(self.fps_label_tag, f"FPS: {current_fps:.1f}")

            # Control playback speed
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_time - elapsed)
            time.sleep(sleep_time)

        cap.release()

        # Reset UI when done
        if not self.is_playing:  # Only if stopped naturally, not by user
            dpg.configure_item(self.play_button_tag, enabled=True)
            dpg.configure_item(self.pause_button_tag, enabled=False, label="Pause")
            dpg.configure_item(self.stop_button_tag, enabled=False)

    def _process_frame(self, frame, frame_number):
        """Process a single frame through the pipeline"""
        if not self.config:
            return frame

        # Resize to output size
        out_w, out_h = self.config['output_size']
        frame = cv2.resize(frame, (out_w, out_h))

        # Detect players
        detections = self.detector.detect(frame)

        # Update tracker
        detections = self.tracker.update(detections)

        # Build tracker positions for analysis
        tracker_positions = {}
        if detections.tracker_id is not None:
            for bbox, tracker_id in zip(detections.xyxy, detections.tracker_id):
                tracker_id = int(tracker_id)
                centroid = self._get_centroid(bbox)
                tracker_positions[tracker_id] = centroid
                self.analyzer.update(tracker_id, centroid)

        # Apply annotations based on settings
        annotated_frame = frame.copy()

        if detections.tracker_id is not None:
            for i, (bbox, tracker_id) in enumerate(zip(detections.xyxy, detections.tracker_id)):
                tracker_id = int(tracker_id)
                centroid = tracker_positions.get(tracker_id, (0, 0))

                # Skip if no valid tracking
                if centroid == (0, 0):
                    continue

                # Get team classification (with caching for performance)
                if tracker_id in self._team_cache:
                    team = self._team_cache[tracker_id]
                else:
                    # If classifier not yet fitted, fit it on current frame detections
                    if not self.classifier_fitted and detections.xyxy is not None and len(detections.xyxy) > 0:
                        self.classifier.fit(frame, detections.xyxy)
                        # Set cluster map from config
                        cluster_map = {int(k): int(v) for k, v in self.config['cluster_map'].items()}
                        self.classifier.set_cluster_map(cluster_map)
                        self.classifier_fitted = True
                    team = self.classifier.predict(frame, bbox)
                    if team != -1:  # Only cache valid teams
                        self._team_cache[tracker_id] = team

                # Get color for this team
                color_tuple = tuple(self.config['team_colors'].get(
                    str(team), self.config['team_colors'].get(team, [255, 255, 255]))
                )

                # Draw annotations based on settings
                if self.config['show_rings']:
                    annotated_frame = draw_glowing_ring(
                        annotated_frame, centroid, color_tuple, radius=25
                    )

                if self.config['show_labels'] and str(tracker_id) in self.config['labels']:
                    label_text = self.config['labels'][str(tracker_id)]
                    label_pos = (centroid[0], centroid[1] + 30)
                    annotated_frame = draw_player_label(
                        annotated_frame, label_text, label_pos, color_tuple
                    )

                if self.config['show_movement_arrows']:
                    arrow_result = self.analyzer.get_run_arrow(tracker_id, centroid)
                    if arrow_result is not None:
                        start_pt, end_pt = arrow_result
                        annotated_frame = draw_dashed_arrow(
                            annotated_frame, start_pt, end_pt, color_tuple,
                            dash_len=12, gap_len=8
                        )

            # Draw connections
            if self.config['show_connections'] and detections.tracker_id is not None:
                for conn in self.config['connections']:
                    id1, id2 = conn
                    if id1 in tracker_positions and id2 in tracker_positions:
                        # Get color from first tracked object
                        team1 = self._team_cache.get(id1, -1)
                        color = tuple(self.config['team_colors'].get(
                            str(team1), self.config['team_colors'].get(team1, [255, 255, 255]))
                        )
                        annotated_frame = draw_connecting_line(
                            annotated_frame,
                            tracker_positions[id1],
                            tracker_positions[id2],
                            color,
                            thickness=2
                        )

            # Draw zones
            if self.config['show_zones'] and detections.tracker_id is not None:
                for zone in self.config['zones']:
                    id1, id2, id3 = zone
                    if id1 in tracker_positions and id2 in tracker_positions and id3 in tracker_positions:
                        pts = [
                            tracker_positions[id1],
                            tracker_positions[id2],
                            tracker_positions[id3]
                        ]

                        # Average color of the three points
                        colors = []
                        for id_ in [id1, id2, id3]:
                            team = self._team_cache.get(id_, -1)
                            if team == -1:
                                color = [200, 200, 200]  # default for other
                            else:
                                color = self.config['team_colors'].get(
                                    str(team), self.config['team_colors'].get(team, [255, 255, 255])
                                )
                            colors.append(color)

                        # Average the colors
                        avg_color = (
                            int(np.mean([c[0] for c in colors])),
                            int(np.mean([c[1] for c in colors])),
                            int(np.mean([c[2] for c in colors]))
                        )

                        annotated_frame = draw_hatched_zone(
                            annotated_frame,
                            pts,
                            tuple(avg_color)
                        )

        return annotated_frame

    def _get_centroid(self, bbox):
        """Calculate centroid of bounding box"""
        x1, y1, x2, y2 = bbox
        return (int((x1 + x2) // 2), int((y1 + y2) // 2))

    def _update_texture(self, frame):
        """Update the Dear PyGui texture with a new frame"""
        if self.texture_texture is None or self.texture_width == 0 or self.texture_height == 0:
            return

        # Convert BGR to RGBA
        frame_rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)

        # Normalize to 0-1 float for Dear PyGui
        frame_normalized = frame_rgba.astype(np.float32) / 255.0

        # Flatten the array for texture update
        flat_data = frame_normalized.flatten()

        # Update the texture
        dpg.set_value(self.video_texture_tag, flat_data)

    def _show_frame(self, frame_number):
        """Display a specific frame without processing"""
        if not self.video_path or not os.path.exists(self.video_path):
            return

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            return

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if ret:
            # Process frame for display
            processed_frame = self._process_frame(frame, frame_number)
            self._update_texture(processed_frame)

    def _callback_save_output(self, sender, app_data):
        """Handle save output dialog"""
        # This would implement saving the processed video
        # For now, just show a placeholder
        with dpg.window(label="Save Output", modal=True, show=True, tag="save_modal"):
            dpg.add_text("Save functionality would be implemented here")
            dpg.add_input_text(hint="Output path", default_value="output/annotated.mp4", width=-1, tag="save_output_input")
            dpg.add_button(label="Save", width=75,
                          callback=lambda: self._actual_save_output(dpg.get_value("save_output_input")))
            dpg.add_button(label="Cancel", width=75,
                          callback=lambda: dpg.delete_item("save_modal"))

    def _actual_save_output(self, output_path):
        """Actually save the processed video"""
        dpg.delete_item("save_modal")
        # Implementation would go here - similar to process_video_loop but writing to file
        # For brevity, this is omitted but would follow similar pattern to _process_video_loop
        pass

    def _callback_reset_view(self, sender, app_data):
        """Reset view to default"""
        # Reset zoom/pan if implemented
        pass

    def _update_ui(self):
        """Update UI elements that need regular updates"""
        # This could be used for periodic updates if needed
        pass

def main():
    """Main entry point for GUI application"""
    app = TacticalAnnotatorGUI()
    app.start_dearpygui()

if __name__ == "__main__":
    main()