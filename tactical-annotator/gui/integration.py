"""
Integration module for Tactical Annotator GUI
Connects GUI components with the existing processing pipeline
"""

import threading
import time
import cv2
import numpy as np
import dearpygui.dearpygui as dpg
from pathlib import Path
import sys

# Add parent directory to path to import existing modules
sys.path.append(str(Path(__file__).parent.parent))

from main import load_config, run_pipeline
from gui.video_display import VideoDisplay
from gui.control_panel import ControlPanel


class GUIIntegration:
    def __init__(self):
        self.video_display = None
        self.control_panel = None
        self.is_running = False
        self.is_paused = False
        self.current_frame = 0
        self.total_frames = 0
        self.fps = 0
        self.video_path = ""
        self.output_path = ""
        self.processing_thread = None
        self.config = None

        # Processing components (initialized on demand)
        self.detector = None
        self.tracker = None
        self.classifier = None
        self.analyzer = None
        self.team_cache = {}

        # Frame buffering for display
        self.latest_frame = None
        self.frame_lock = threading.Lock()

    def initialize(self):
        """Initialize GUI components"""
        # Initialize Dear PyGui context
        dpg.create_context()
        dpg.create_viewport(title='Tactical Analyst', width=1400, height=900)

        # Set up theme (optional - use default for now)
        #1

        # Create UI components
        self._setup_ui()

        # Setup viewport
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("primary_window", True)

    def _setup_ui(self):
        """Set up the user interface"""
        with dpg.window(label="Tactical Analyst - Football Video Annotation", tag="primary_window"):
            # Main display area (left side)
            with dpg.group(horizontal=True):
                # Video display
                with dpg.child_window(width=900, height=700, border=True, tag="video_container"):
                    # Placeholder for video texture
                    dpg.add_text("Load a video to begin analysis",
                                pos=(400, 350),
                                tag="video_placeholder",
                                color=[200, 200, 200])

                # Control panel
                with dpg.child_window(width=400, height=700, border=True, tag="control_panel"):
                    # Controls will be added here by ControlPanel
                    pass

        # Initialize components
        self.video_display = VideoDisplay()
        self.control_panel = ControlPanel(config_callback=self._on_config_change)

        # Create controls in the control panel container
        self.control_panel.create_controls("control_panel")

        # Set up callbacks
        self._setup_callbacks()

    def _setup_callbacks(self):
        """Set up all callback functions"""
        # File callbacks
        self.control_panel.set_file_callback(self._on_load_video)
        self.control_panel.set_menu_callbacks(
            open_cb=self._on_load_video,
            exit_cb=self._on_exit
        )

        # Playback callbacks
        self.control_panel.set_playback_callbacks(
            play_cb=self._on_play,
            pause_cb=self._on_pause,
            stop_cb=self._on_stop
        )

        # Slider callbacks
        self.control_panel.set_frame_slider_callback(self._on_frame_seek)
        self.control_panel.set_parameter_callbacks(self._on_parameter_change)

        # Annotation callbacks
        self.control_panel.set_annotation_callbacks(self._on_annotation_toggle)

    def _on_load_video(self, sender, app_data):
        """Handle video file loading"""
        # Handle both direct file path and file dialog return formats
        if isinstance(app_data, str):
            file_path = app_data
        elif isinstance(app_data, dict) and 'selections' in app_data:
            # File dialog return format
            file_path = list(app_data['selections'].values())[0] if app_data['selections'] else ""
        else:
            return

        if not file_path or not self._is_valid_video_file(file_path):
            self._show_error("Invalid file", "Please select a valid video file")
            return

        self.video_path = file_path
        self.control_panel.update_video_path(file_path)

        # Load video info
        self._load_video_info()

        # Initialize processing components
        self._initialize_processors()

        # Clear placeholder
        if dpg.does_item_exist("video_placeholder"):
            dpg.delete_item("video_placeholder")

    def _is_valid_video_file(self, filepath: str) -> bool:
        """Check if file is a valid video file"""
        if not filepath or not isinstance(filepath, str):
            return False

        # Check extension
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
        ext = '.' + filepath.lower().split('.')[-1] if '.' in filepath else ''
        return ext in video_extensions

    def _load_video_info(self):
        """Load video metadata"""
        if not self.video_path:
            return

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            self._show_error("Error", "Could not open video file")
            return

        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        cap.release()

        # Update UI
        self.control_panel.update_frame_info(0, self.total_frames, self.fps)

        # Initialize video display with video dimensions
        self.video_display.initialize(width, height)

        # Set up texture in the video container
        self._setup_video_texture()

    def _setup_video_texture(self):
        """Set up the video texture in the GUI"""
        # This would typically involve setting up the texture registry
        # and binding it to an image widget. For simplicity in this example,
        # we'll rely on the VideoDisplay class to handle this internally.
        pass

    def _initialize_processors(self):
        """Initialize the video processing pipeline components"""
        try:
            # Load base configuration
            self.config = load_config('config.yaml')
            if not self.config:
                self._show_error("Error", "Could not load configuration")
                return

            # Apply current GUI settings to config
            self.control_panel.get_current_config()
            self.config.update(self.control_panel.current_config)

            # Initialize processing components
            self.detector = self._create_detector()
            self.tracker = self._create_tracker()
            self.classifier = self._create_classifier()
            self.analyzer = self._create_analyzer()

        except Exception as e:
            self._show_error("Initialization Error", f"Failed to initialize processors: {str(e)}")

    def _create_detector(self):
        """Create and return the detector instance"""
        from modules.detector import PlayerDetector
        return self.detector.__class__(
            self.config['model_path'],
            self.config['confidence']
        )

    def _create_tracker(self):
        """Create and return the tracker instance"""
        from modules.tracker import PlayerTracker
        return self.tracker.__class__(
            lost_track_buffer=self.config['lost_track_buffer'],
            min_matching_threshold=self.config['min_matching_threshold']
        )

    def _create_classifier(self):
        """Create and return the classifier instance"""
        from modules.classifier import TeamClassifier
        return self.classifier.__class__(n_clusters=3)

    def _create_analyzer(self):
        """Create and return the analyzer instance"""
        from modules.analyzer import MovementAnalyzer
        return self.analyzer.__class__(
            history_len=self.config['history_frames'],
            run_threshold=self.config['run_threshold']
        )

    def _on_play(self, sender, app_data):
        """Handle play button press"""
        if not self.video_path:
            self._show_error("No Video", "Please load a video first")
            return

        self.is_running = True
        self.is_paused = False

        # Update button states
        self.control_panel.set_playback_state(True, False)

        # Start processing thread
        if self.processing_thread is None or not self.processing_thread.is_alive():
            self.processing_thread = threading.Thread(target=self._processing_loop)
            self.processing_thread.daemon = True
            self.processing_thread.start()

    def _on_pause(self, sender, app_data):
        """Handle pause button press"""
        self.is_paused = not self.is_paused
        self.control_panel.set_playback_state(self.is_running, self.is_paused)

        # Update button label
        if dpg.does_item_exist("pause_button"):
            label = "Resume" if self.is_paused else "Pause"
            dpg.set_item_label("pause_button", label)

    def _on_stop(self, sender, app_data):
        """Handle stop button press"""
        self.is_running = False
        self.is_paused = False
        self.current_frame = 0

        # Update button states
        self.control_panel.set_playback_state(False, False)
        if dpg.does_item_exist("pause_button"):
            dpg.set_item_label("pause_button", "Pause")

        # Reset UI
        self.control_panel.update_frame_info(0, self.total_frames, self.fps)
        if self.video_display and self.total_frames > 0:
            # Show first frame
            self._display_frame_at_position(0)

    def _on_frame_seek(self, sender, app_data):
        """Handle frame slider movement"""
        if not self.is_running:  # Only allow seeking when not playing
            frame_num = int(app_data)
            self.current_frame = frame_num
            self._display_frame_at_position(frame_num)
            self.control_panel.update_frame_info(
                frame_num, self.total_frames, self.fps)

    def _on_parameter_change(self, sender, app_data):
        """Handle parameter slider changes"""
        # Update configuration
        self.control_panel.get_current_config()
        if self.config:
            self.config.update(self.control_panel.current_config)

        # If we have a paused video, update the current frame
        if not self.is_running and self.video_path:
            self._display_frame_at_position(self.current_frame)

    def _on_annotation_toggle(self, sender, app_data):
        """Handle annotation toggle changes"""
        self.control_panel.get_current_config()
        if self.config:
            self.config.update(self.control_panel.current_config)

        # If we have a paused video, update the current frame
        if not self.is_running and self.video_path:
            self._display_frame_at_position(self.current_frame)

    def _on_exit(self, sender, app_data):
        """Handle exit application"""
        self.is_running = False
        dpg.stop_dearpygui()

    def _processing_loop(self):
        """Main video processing loop"""
        if not self.video_path:
            return

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            self._show_error("Error", "Could not open video for processing")
            self.is_running = False
            return

        # Set starting position
        cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)

        frame_time = 1.0 / self.fps if self.fps > 0 else 1.0 / 30.0

        while self.is_running and cap.isOpened():
            if self.is_paused:
                time.sleep(0.1)
                continue

            start_time = time.time()

            ret, frame = cap.read()
            if not ret:
                # End of video
                self.is_running = False
                break

            # Process frame
            processed_frame = self._process_frame(
                frame,
                int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
            )

            # Update display
            with self.frame_lock:
                self.latest_frame = processed_frame.copy()

            # Update frame counter
            self.current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))

            # Update UI (thread-safe)
            try:
                if dpg.is_dearpygui_running():
                    # Use a thread-safe way to update UI
                    def update_ui():
                        self._update_display_from_frame(processed_frame)
                        self.control_panel.update_frame_info(
                            self.current_frame, self.total_frames, self.fps
                        )

                    # Schedule update on main thread
                    dpg.set_frame_callback(1, lambda: update_ui())
            except:
                pass  # Ignore UI update errors during shutdown

            # Calculate and display FPS
            elapsed = time.time() - start_time
            if elapsed > 0:
                current_fps = 1.0 / elapsed
                try:
                    if dpg.is_dearpygui_running():
                        dpg.set_value("fps_label", f"FPS: {current_fps:.1f}")
                except:
                    pass

            # Control playback speed
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_time - elapsed)
            time.sleep(sleep_time)

        cap.release()

        # Final cleanup
        self.is_running = False
        try:
            if dpg.is_dearpygui_running():
                self.control_panel.set_playback_state(False, False)
                if dpg.does_item_exist("pause_button"):
                    dpg.set_item_label("pause_button", "Pause")
        except:
            pass

    def _process_frame(self, frame: np.ndarray, frame_number: int) -> np.ndarray:
        """
        Process a single frame through the pipeline

        Args:
            frame: Input frame (BGR format)
            frame_number: Current frame number

        Returns:
            Processed frame with annotations (BGR format)
        """
        if not self.config or not all([self.detector, self.tracker, self.classifier, self.analyzer]):
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

        # Apply annotations
        annotated_frame = frame.copy()

        if detections.tracker_id is not None:
            for i, (bbox, tracker_id) in enumerate(zip(detections.xyxy, detections.tracker_id)):
                tracker_id = int(tracker_id)
                centroid = tracker_positions.get(tracker_id, (0, 0))

                # Skip if no valid tracking
                if centroid == (0, 0):
                    continue

                # Get team classification with caching
                if tracker_id in self.team_cache:
                    team = self.team_cache[tracker_id]
                else:
                    team = self.classifier.predict(frame, bbox)
                    if team != -1:  # Only cache valid team assignments
                        self.team_cache[tracker_id] = team

                # Get color for this team
                team_key = str(team)
                color_list = self.config['team_colors'].get(
                    team_key,
                    self.config['team_colors'].get(team, [255, 255, 255])
                )
                color = tuple(map(int, color_list))  # Ensure integers

                # Apply annotations based on settings
                if self.config['show_rings']:
                    annotated_frame = draw_glowing_ring(
                        annotated_frame, centroid, color, radius=25
                    )

                if self.config['show_labels'] and str(tracker_id) in self.config['labels']:
                    label_text = self.config['labels'][str(tracker_id)]
                    label_pos = (centroid[0], centroid[1] + 30)
                    annotated_frame = draw_player_label(
                        annotated_frame, label_text, label_pos, color
                    )

                if self.config['show_movement_arrows']:
                    arrow_result = self.analyzer.get_run_arrow(tracker_id, centroid)
                    if arrow_result is not None:
                        start_pt, end_pt = arrow_result
                        annotated_frame = draw_dashed_arrow(
                            annotated_frame, start_pt, end_pt, color,
                            dash_len=12, gap_len=8
                        )

            # Draw connections between players
            if self.config['show_connections']:
                for conn in self.config['connections']:
                    id1, id2 = conn
                    if id1 in tracker_positions and id2 in tracker_positions:
                        # Get color from first tracked object
                        team1 = self.team_cache.get(id1, -1)
                        team_key = str(team1)
                        color_list = self.config['team_colors'].get(
                            team_key,
                            self.config['team_colors'].get(team1, [255, 255, 255])
                        )
                        color = tuple(map(int, color_list))
                        annotated_frame = draw_connecting_line(
                            annotated_frame,
                            tracker_positions[id1],
                            tracker_positions[id2],
                            color,
                            thickness=2
                        )

        return annotated_frame

    def _get_centroid(self, bbox: np.ndarray) -> tuple:
        """Calculate centroid of bounding box"""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def _update_display_from_frame(self, frame: np.ndarray):
        """Update the display with a processed frame"""
        if frame is None:
            return

        # Convert BGR to RGB for display
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Update video display
        self.video_display.update_frame(rgb_frame)

        # In a full implementation, we would update the texture here
        # For this example, we rely on the VideoDisplay class

    def _display_frame_at_position(self, frame_number: int):
        """Display a specific frame without processing"""
        if not self.video_path:
            return

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            return

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if ret:
            # Process the frame for display
            processed_frame = self._process_frame(frame, frame_number)
            self._update_display_from_frame(processed_frame)

    def _show_error(self, title: str, message: str):
        """Show an error dialog"""
        with dpg.window(label=title, modal=True, show=True, tag="error_modal"):
            dpg.add_text(message)
            dpg.add_button(label="OK", width=75,
                          callback=lambda: dpg.delete_item("error_modal"))

    def render_loop(self):
        """Main render loop"""
        while dpg.is_dearpygui_running():
            # Update the video display with the latest frame
            with self.frame_lock:
                if self.latest_frame is not None:
                    self._update_display_from_frame(self.latest_frame)

            # Render Dear PyGui frame
            dpg.render_dearpygui_frame()
            time.sleep(0.016)  # ~60 FPS

        # Cleanup
        self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        self.is_running = False
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=1.0)

        if dpg.is_dearpygui_running():
            dpg.destroy_context()

    def run(self):
        """Run the GUI application"""
        try:
            self.initialize()
            self.render_loop()
        except Exception as e:
            print(f"Error running GUI: {e}")
            self.cleanup()


def main():
    """Main entry point for the GUI application"""
    app = GUIIntegration()
    app.run()


if __name__ == "__main__":
    main()