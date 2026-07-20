import argparse
import os
import cv2
import yaml
import numpy as np
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


def load_config(config_path):
    """
    Load configuration from a YAML file.
    """
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def get_centroid(bbox: np.ndarray) -> tuple[int, int]:
    """
    Calculate centroid of a bounding box.
    bbox: [x1, y1, x2, y2]
    """
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) // 2, (y1 + y2) // 2)

def run_inspect(config, frame_num: int, classify_only: bool):
    """
    Inspect a single frame for debugging.
    """
    # Initialize detector
    detector = PlayerDetector(config['model_path'], config['confidence'])

    # Open video
    cap = cv2.VideoCapture(config['input_video'])
    if not cap.isOpened():
        raise IOError(f"Cannot open video file {config['input_video']}")

    # Seek to the frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise IOError(f"Cannot read frame {frame_num}")

    # Resize to output size if needed
    out_w, out_h = config['output_size']
    frame = cv2.resize(frame, (out_w, out_h))

    # Run detection
    detections = detector.detect(frame)

    if classify_only:
        # Only run detection and classification
        classifier = TeamClassifier(n_clusters=3)
        # Fit classifier on detections of this frame
        classifier.fit(frame, detections.xyxy)
        # Set cluster map to identity for raw cluster inspection
        classifier.set_cluster_map({0: 0, 1: 1, 2: 2})

        # For each detection, get centroid, predict cluster, compute mean HSV
        for i, (bbox, _) in enumerate(zip(detections.xyxy, detections.confidence)):
            centroid = get_centroid(bbox)
            cluster = classifier.predict(frame, bbox)
            # Recompute mean HSV for printing
            crop = classifier._crop_jersey(frame, bbox)
            mean_hsv = classifier._get_mean_hsv(crop)
            print(f"det_idx={i}, bbox={bbox}, centroid={centroid}, cluster={cluster}, mean_HSV={mean_hsv}")
            # Draw cluster number on frame
            cv2.putText(frame, str(cluster), centroid, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)

        # Save the frame
        output_path = f"output/inspect_frame_{frame_num}_classify.png"
        cv2.imwrite(output_path, frame)
        print(f"Saved inspection frame to {output_path}")
    else:
        # Full inspection: detection, tracking, classification
        tracker = PlayerTracker(
            lost_track_buffer=config['lost_track_buffer'],
            min_matching_threshold=config['min_matching_threshold']
        )
        classifier = TeamClassifier(n_clusters=3)
        classifier.fit(frame, detections.xyxy)
        # Use cluster map from config (keys may be strings, convert to int)
        cluster_map = {int(k): int(v) for k, v in config['cluster_map'].items()}
        classifier.set_cluster_map(cluster_map)

        # Update tracker
        detections = tracker.update(detections)

        # For each tracked detection, print and draw
        if detections.tracker_id is not None:
            for i, (bbox, tracker_id) in enumerate(zip(detections.xyxy, detections.tracker_id)):
                tracker_id = int(tracker_id)
                centroid = get_centroid(bbox)
                team = classifier.predict(frame, bbox)
                # Get color from config
                color = config['team_colors'].get(str(team), config['team_colors'].get(team, [255, 255, 255]))
                print(f"tracker_id={tracker_id}, team={team}, centroid={centroid}")
                # Draw a circle in team color
                cv2.circle(frame, centroid, 10, color, 2)
                # Put text above
                text = f"id:{tracker_id} t:{team}"
                cv2.putText(frame, text, (centroid[0], centroid[1] - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)

        # Save the frame
        output_path = f"output/inspect_frame_{frame_num}.png"
        cv2.imwrite(output_path, frame)
        print(f"Saved inspection frame to {output_path}")

def run_pipeline(config, start_frame: int, end_frame: int):
    """
    Main processing loop for the video.
    """
    # Initialize modules
    detector = PlayerDetector(config['model_path'], config['confidence'])
    tracker = PlayerTracker(
        lost_track_buffer=config['lost_track_buffer'],
        min_matching_threshold=config['min_matching_threshold']
    )
    classifier = TeamClassifier(n_clusters=3)
    analyzer = MovementAnalyzer(
        history_len=config['history_frames'],
        run_threshold=config['run_threshold']
    )

    # Open video
    cap = cv2.VideoCapture(config['input_video'])
    if not cap.isOpened():
        raise IOError(f"Cannot open video file {config['input_video']}")

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if end_frame is None or end_frame > total_frames:
        end_frame = total_frames

    # Set up video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_w, out_h = config['output_size']
    out = cv2.VideoWriter(
        config['output_video'],
        fourcc,
        config['output_fps'],
        (out_w, out_h)
    )

    # Process first frame to fit classifier
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret, first_frame = cap.read()
    if not ret:
        raise IOError("Cannot read first frame")
    first_frame = cv2.resize(first_frame, (out_w, out_h))
    first_detections = detector.detect(first_frame)
    classifier.fit(first_frame, first_detections.xyxy)
    # Set cluster map from config
    cluster_map = {int(k): int(v) for k, v in config['cluster_map'].items()}
    classifier.set_cluster_map(cluster_map)

    # Reset to start frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    # Persistent cache for team assignments per tracker_id
    tracker_team_cache = {}  # tracker_id -> team

    frame_count = start_frame
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret or frame_count >= end_frame:
            break

        frame_count += 1

        # Resize frame
        frame = cv2.resize(frame, (out_w, out_h))

        # Detect players
        detections = detector.detect(frame)

        # Update tracker
        detections = tracker.update(detections)

        # Build tracker_positions dict: tracker_id -> centroid
        tracker_positions = {}
        if detections.tracker_id is not None:
            for bbox, tracker_id in zip(detections.xyxy, detections.tracker_id):
                tracker_id = int(tracker_id)
                centroid = get_centroid(bbox)
                tracker_positions[tracker_id] = centroid
                # Update analyzer with this position
                analyzer.update(tracker_id, centroid)
                # Get team from cache or classify
                if tracker_id not in tracker_team_cache:
                    team = classifier.predict(frame, bbox)
                    if team != -1:  # Only cache if we have a valid team
                        tracker_team_cache[tracker_id] = team
                else:
                    team = tracker_team_cache[tracker_id]

                # Get color for this team
                color = tuple(config['team_colors'].get(str(team), config['team_colors'].get(team, [255, 255, 255])))

                # Draw glowing ring if enabled
                if config['show_rings']:
                    frame = draw_glowing_ring(frame, centroid, color, radius=25)

                # Draw label if present in config
                if str(tracker_id) in config['labels']:
                    label_text = config['labels'][str(tracker_id)]
                    # Position below centroid
                    label_pos = (centroid[0], centroid[1] + 30)
                    frame = draw_player_label(frame, label_text, label_pos, color)

                # Draw movement arrow if enabled
                if config['show_movement_arrows']:
                    arrow_result = analyzer.get_run_arrow(tracker_id, centroid)
                    if arrow_result is not None:
                        start_pt, end_pt = arrow_result
                        frame = draw_dashed_arrow(frame, start_pt, end_pt, color,
                                                  dash_len=12, gap_len=8)

        # Draw connections if enabled
        if config['show_connections'] and detections.tracker_id is not None:
            for conn in config['connections']:
                id1, id2 = conn
                if id1 in tracker_positions and id2 in tracker_positions:
                    # Get teams for both IDs (from cache)
                    team1 = tracker_team_cache.get(id1, -1)
                    team2 = tracker_team_cache.get(id2, -1)
                    # We'll draw the line regardless of team (as per spec)
                    # But if we want to color by team, we could use one of them or average.
                    # For simplicity, we'll use the color of the first ID.
                    color = tuple(config['team_colors'].get(str(team1), config['team_colors'].get(team1, [255, 255, 255])))
                    frame = draw_connecting_line(frame, tracker_positions[id1], tracker_positions[id2], color, thickness=2)

        # Draw zones if enabled
        if config['show_zones'] and detections.tracker_id is not None:
            for zone in config['zones']:
                id1, id2, id3 = zone
                if id1 in tracker_positions and id2 in tracker_positions and id3 in tracker_positions:
                    # Get the three points
                    pts = [tracker_positions[id1], tracker_positions[id2], tracker_positions[id3]]
                    # We need a color for the zone; we can average the colors of the three players
                    colors = []
                    for id_ in [id1, id2, id3]:
                        team = tracker_team_cache.get(id_, -1)
                        if team == -1:
                            color = [200, 200, 200]  # default for other
                        else:
                            color = config['team_colors'].get(str(team), config['team_colors'].get(team, [255, 255, 255]))
                        colors.append(color)
                    # Average the colors
                    avg_color = (
                        int(np.mean([c[0] for c in colors])),
                        int(np.mean([c[1] for c in colors])),
                        int(np.mean([c[2] for c in colors]))
                    )
                    frame = draw_hatched_zone(frame, pts, tuple(avg_color))

        # Write frame to output video
        out.write(frame)

        # Print progress
        if frame_count % 30 == 0:
            print(f"Processed frame {frame_count}")

    # Release resources
    cap.release()
    out.release()
    print(f"Processing complete. Output saved to {config['output_video']}")

def main():
    parser = argparse.ArgumentParser(description='Tactical Football Video Annotation Pipeline')
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to config.yaml')
    parser.add_argument('--inspect-frame', type=int, help='Frame number to inspect (for debugging)')
    parser.add_argument('--classify-only', action='store_true', help='Only run detection and classification (no tracking)')
    parser.add_argument('--start-frame', type=int, default=0, help='Start frame for processing')
    parser.add_argument('--end-frame', type=int, default=None, help='End frame for processing (exclusive)')
    parser.add_argument('--gui', action='store_true', help='Launch graphical user interface')
    args = parser.parse_args()

    # Ensure output directory exists
    os.makedirs('output', exist_ok=True)

    if args.gui:
        # Launch GUI
        from gui.main_gui import TacticalAnnotatorGUI
        app = TacticalAnnotatorGUI()
        app.start_dearpygui()
    elif args.inspect_frame is not None:
        config = load_config(args.config)
        run_inspect(config, args.inspect_frame, args.classify_only)
    else:
        config = load_config(args.config)
        run_pipeline(config, args.start_frame, args.end_frame)

if __name__ == '__main__':
    main()