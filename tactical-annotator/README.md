# Tactical Annotator

A computer vision system for analyzing and annotating football (soccer) match videos with tactical insights.

## Features

- Player detection using YOLOv8
- Multi-object tracking with ByteTracker
- Team classification via jersey color clustering
- Movement analysis to detect runs and sprints
- Tactical visualization including:
  - Glowing rings around players
  - Connection lines between players
  - Zones highlighting tactical formations
  - Movement arrows indicating runs
  - Player labels with names/numbers

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Command Line Interface

Process a video with default settings:
```bash
python main.py --input-video input/clip.mp4 --output-video output/annotated.mp4
```

Process a specific frame range:
```bash
python main.py --start-frame 0 --end-frame 300 --input-video input/clip.mp4 --output-video output/annotated.mp4
```

Inspect a specific frame for debugging:
```bash
python main.py --inspect-frame 150 --classify-only
```

### Graphical User Interface

Launch the GUI for interactive video analysis:
```bash
python main.py --gui
```

The GUI provides:
- Real-time video playback with annotations
- File browser for easy video selection
- Playback controls (play, pause, stop, frame seek)
- Interactive parameter adjustment (confidence, thresholds, etc.)
- Toggle switches for annotation types (rings, connections, zones, arrows, labels)
- Frame-by-frame navigation for detailed analysis
- Real-time FPS counter

## Configuration

Adjust detection and tracking parameters in `config.yaml`:
- `confidence`: Detection confidence threshold (0.0-1.0)
- `history_frames`: Number of frames to keep in movement analysis history
- `run_threshold`: Pixel movement threshold to qualify as a run
- Team colors and cluster mappings
- Annotation visibility toggles

## Output

The system produces an annotated video file showing:
- Colored rings around players indicating team possession
- Lines connecting specified player pairs (configurable)
- Semi-transparent zones highlighting tactical formations
- Dashed arrows showing player movement and runs
- Text labels with player IDs/names (when configured)

## Requirements

See `requirements.txt` for detailed dependencies.
Key components:
- OpenCV for video processing
- Ultralytics YOLOv8 for player detection
- Supervision for tracking utilities
- Scikit-learn for team classification
- Dear PyGui for graphical interface (when using --gui flag)

## Model

The system uses a YOLOv8 model trained for football player detection.
To download a model, run:
```bash
python download_model.py
```
Choose between Roboflow (football-specific) or Ultralytics (general) models.

## GUI Usage Tips

1. **Loading Video**: Click "Load Video" or use File → Open Video to select a video file
2. **Playback**: Use Play/Pause/Stop buttons or the frame slider to navigate
3. **Parameters**: Adjust sliders in real-time to see immediate effects on detection
4. **Annotations**: Toggle checkboxes to show/hide different annotation types
5. **Analysis**: Pause at specific frames to examine detailed annotations
6. **Performance**: The GUI is optimized for real-time display, but processing speed depends on your hardware and video resolution

## Notes

- The GUI preserves all command-line functionality
- Processing happens in a background thread to keep the interface responsive
- Close the GUI window or use File → Exit to quit the application
- For best performance, use videos with resolutions matching the configured output size