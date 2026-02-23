import sys
import argparse

from PyQt5.QtWidgets import QApplication

from config.settings import AppSettings
from processing.pipeline import ProcessingPipeline
from processing.touch_router import TouchRouter
from tuio.sender import TuioSender
from gui.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser(description="LiDAR Touch - OptiTUIO-style Application")
    parser.add_argument("--mock", action="store_true",
                        help="Use mock LiDAR scanner (no hardware required)")
    parser.add_argument("--settings", type=str, default="settings.json",
                        help="Path to settings JSON file")
    args = parser.parse_args()

    # Load or create settings
    try:
        settings = AppSettings.load(args.settings)
    except (FileNotFoundError, Exception):
        settings = AppSettings()

    app = QApplication(sys.argv)
    app.setApplicationName("LiDAR Touch")

    snap = settings.get_snapshot()

    # Create per-sensor scanner + pipeline
    scanners = []
    pipelines = []
    for i, sensor_cfg in enumerate(snap['sensors']):
        if args.mock:
            from lidar.mock_scanner import MockLidarScanner
            scanner = MockLidarScanner(num_touches=2)
        else:
            from lidar.scanner import LidarScanner
            scanner = LidarScanner(sensor_cfg['lidar_ip'], sensor_cfg['lidar_port'])
        pipeline = ProcessingPipeline(settings, sensor_index=i)
        scanner.scan_ready.connect(pipeline.enqueue_scan)
        scanners.append(scanner)
        pipelines.append(pipeline)

    # Create per-output TUIO sender
    tuio_senders = []
    for output_cfg in snap['outputs']:
        sender = TuioSender(
            output_cfg['tuio_host'],
            output_cfg['tuio_port'],
            source_name=output_cfg.get('name', 'HokuyoTouch'),
        )
        sender.enabled = output_cfg.get('tuio_enabled', True)
        tuio_senders.append(sender)

    # Create touch router
    touch_router = TouchRouter(settings)
    for pipeline in pipelines:
        pipeline.touches_updated.connect(touch_router.route_touches)

    # Route screen touches to TUIO senders
    def dispatch_touches(screen_index, touches, frame_seq):
        current_snap = settings.get_snapshot()
        for oi, output_cfg in enumerate(current_snap.get('outputs', [])):
            if oi < len(tuio_senders) and output_cfg.get('screen_index', 0) == screen_index:
                tuio_senders[oi].send_frame(touches, frame_seq)

    touch_router.screen_touches.connect(dispatch_touches)

    # Create main window
    window = MainWindow(settings, scanners, pipelines, tuio_senders, touch_router, mock_mode=args.mock)
    window._settings_path = args.settings

    # Start all pipeline threads
    for pipeline in pipelines:
        pipeline.start()

    # In mock mode, auto-start all scanners
    if args.mock:
        for i, scanner in enumerate(scanners):
            scanner.start()
            window.control_panel.devices.set_connection_status("mock", sensor_index=i)

    window.show()
    exit_code = app.exec_()

    # Graceful shutdown
    for scanner in scanners:
        scanner.stop()
    for pipeline in pipelines:
        pipeline.stop()

    # Save settings
    try:
        settings.save(args.settings)
    except Exception:
        pass

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
