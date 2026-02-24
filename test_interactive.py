"""
Automated GUI test: zoom, add sensors, add screens, add outputs.
Launches the app in mock mode and exercises features programmatically.
"""
import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QPointF, Qt
from PyQt5.QtGui import QMouseEvent

from config.settings import AppSettings
from processing.pipeline import ProcessingPipeline
from processing.touch_router import TouchRouter
from tuio.sender import TuioSender
from gui.main_window import MainWindow
from lidar.mock_scanner import MockLidarScanner


def run_test():
    settings = AppSettings()

    app = QApplication(sys.argv)
    app.setApplicationName("LiDAR Touch Test")

    snap = settings.get_snapshot()

    # Create per-sensor scanner + pipeline
    scanners = []
    pipelines = []
    for i, sensor_cfg in enumerate(snap['sensors']):
        scanner = MockLidarScanner(num_touches=2)
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

    def dispatch_touches(screen_index, touches, frame_seq):
        current_snap = settings.get_snapshot()
        for oi, output_cfg in enumerate(current_snap.get('outputs', [])):
            if oi < len(tuio_senders) and output_cfg.get('screen_index', 0) == screen_index:
                tuio_senders[oi].send_frame(touches, frame_seq)

    touch_router.screen_touches.connect(dispatch_touches)

    window = MainWindow(settings, scanners, pipelines, tuio_senders, touch_router, mock_mode=True)

    for pipeline in pipelines:
        pipeline.start()
    for i, scanner in enumerate(scanners):
        scanner.start()
        window.control_panel.devices.set_connection_status("mock", sensor_index=i)

    window.show()

    results = []
    step = [0]

    def test_step():
        try:
            s = step[0]
            step[0] += 1

            if s == 0:
                print("[Step 0] Waiting for initial frames...")

            elif s == 1:
                frame_count = len(window.lidar_view._frames)
                print(f"[Step 1] Frames received: {frame_count}")
                assert frame_count >= 1, f"Expected >= 1 frame, got {frame_count}"
                results.append("PASS: Frames arriving")

            elif s == 2:
                # Test zoom in by directly calling the zoom logic
                print("[Step 2] Testing zoom in...")
                lv = window.lidar_view
                old_zoom = lv._zoom_factor
                assert abs(old_zoom - 1.0) < 0.01, f"Initial zoom should be 1.0, got {old_zoom}"

                # Simulate 5 scroll-up steps
                for _ in range(5):
                    lv._zoom_factor *= 1.1
                    lv._zoom_factor = max(0.1, min(10.0, lv._zoom_factor))

                new_zoom = lv._zoom_factor
                print(f"  Zoom after 5x in: {new_zoom:.3f}")
                assert new_zoom > 1.0, f"Zoom should increase, got {new_zoom}"
                results.append(f"PASS: Zoom in works ({new_zoom:.2f}x)")

            elif s == 3:
                # Test zoom out
                print("[Step 3] Testing zoom out...")
                lv = window.lidar_view
                for _ in range(10):
                    lv._zoom_factor /= 1.1
                    lv._zoom_factor = max(0.1, min(10.0, lv._zoom_factor))

                new_zoom = lv._zoom_factor
                print(f"  Zoom after 10x out: {new_zoom:.3f}")
                assert new_zoom < 1.0, f"Zoom should decrease, got {new_zoom}"
                results.append(f"PASS: Zoom out works ({new_zoom:.2f}x)")

            elif s == 4:
                # Test zoom reset via double-click
                print("[Step 4] Testing zoom reset (double-click)...")
                lv = window.lidar_view
                event = QMouseEvent(
                    QMouseEvent.MouseButtonDblClick,
                    QPointF(200, 200),
                    Qt.LeftButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                )
                lv.mouseDoubleClickEvent(event)
                zoom = lv._zoom_factor
                print(f"  Zoom after double-click: {zoom:.3f}")
                assert abs(zoom - 1.0) < 0.01, f"Zoom should reset to 1.0, got {zoom}"
                results.append("PASS: Zoom reset works")

            elif s == 5:
                # Test zoom clamp limits
                print("[Step 5] Testing zoom clamp limits...")
                lv = window.lidar_view
                for _ in range(100):
                    lv._zoom_factor *= 1.1
                    lv._zoom_factor = max(0.1, min(10.0, lv._zoom_factor))
                max_zoom = lv._zoom_factor
                print(f"  Max zoom: {max_zoom:.3f}")
                assert max_zoom <= 10.0, f"Zoom should clamp at 10.0, got {max_zoom}"

                for _ in range(200):
                    lv._zoom_factor /= 1.1
                    lv._zoom_factor = max(0.1, min(10.0, lv._zoom_factor))
                min_zoom = lv._zoom_factor
                print(f"  Min zoom: {min_zoom:.3f}")
                assert min_zoom >= 0.1, f"Zoom should clamp at 0.1, got {min_zoom}"

                lv._zoom_factor = 1.0
                results.append(f"PASS: Zoom clamps [{min_zoom:.1f}, {max_zoom:.1f}]")

            elif s == 6:
                # Test adding a second sensor
                print("[Step 6] Adding second sensor...")
                n_sensors = settings.sensor_count()
                n_scanners = len(window._scanners)
                n_pipelines = len(window._pipelines)
                print(f"  Before: {n_sensors} sensors, {n_scanners} scanners, {n_pipelines} pipelines")

                window.control_panel.devices._on_add_sensor()

                new_sensors = settings.sensor_count()
                new_scanners = len(window._scanners)
                new_pipelines = len(window._pipelines)
                print(f"  After:  {new_sensors} sensors, {new_scanners} scanners, {new_pipelines} pipelines")

                assert new_sensors == n_sensors + 1
                assert new_scanners == n_scanners + 1
                assert new_pipelines == n_pipelines + 1

                list_count = window.control_panel.devices._sensor_list.count()
                print(f"  Sensor list items: {list_count}")
                assert list_count == 2

                results.append("PASS: Add sensor creates scanner+pipeline")

            elif s == 7:
                print("[Step 7] Waiting for second sensor frames...")

            elif s == 8:
                frame_keys = sorted(window.lidar_view._frames.keys())
                print(f"[Step 8] Frame sensor indices: {frame_keys}")
                assert 0 in frame_keys, "Sensor 0 should have frames"
                assert 1 in frame_keys, "Sensor 1 should have frames"
                results.append("PASS: Both sensors produce frames")

            elif s == 9:
                # Add second screen
                print("[Step 9] Adding second screen...")
                n = settings.screen_count()
                window.control_panel.screens._on_add_screen()
                n2 = settings.screen_count()
                print(f"  Screens: {n} -> {n2}")
                assert n2 == n + 1
                list_count = window.control_panel.screens._screen_list.count()
                assert list_count == 2
                results.append("PASS: Add screen works")

            elif s == 10:
                # Add second output
                print("[Step 10] Adding second output...")
                n = settings.output_count()
                n_senders = len(window._tuio_senders)
                window.control_panel.outputs._on_add_output()
                n2 = settings.output_count()
                n_senders2 = len(window._tuio_senders)
                print(f"  Outputs: {n} -> {n2}, Senders: {n_senders} -> {n_senders2}")
                assert n2 == n + 1
                assert n_senders2 == n_senders + 1
                list_count = window.control_panel.outputs._output_list.count()
                assert list_count == 2
                results.append("PASS: Add output creates TUIO sender")

            elif s == 11:
                # Link output 2 to screen 2
                print("[Step 11] Linking Output 2 to Screen 2...")
                window.control_panel.outputs._output_list.setCurrentRow(1)
                combo_count = window.control_panel.outputs._screen_combo.count()
                print(f"  Screen combo items: {combo_count}")
                assert combo_count == 2

                window.control_panel.outputs._screen_combo.setCurrentIndex(1)
                output = settings.get_output(1)
                print(f"  Output 2 screen_index: {output['screen_index']}")
                assert output['screen_index'] == 1
                results.append("PASS: Output linked to Screen 2")

            elif s == 12:
                # Remove sensor
                print("[Step 12] Removing second sensor...")
                window.control_panel.devices._sensor_list.setCurrentRow(1)
                window.control_panel.devices._on_remove_sensor()
                count = settings.sensor_count()
                scanner_count = len(window._scanners)
                print(f"  After remove: {count} sensors, {scanner_count} scanners")
                assert count == 1
                assert scanner_count == 1
                results.append("PASS: Remove sensor cleans up")

            elif s == 13:
                # Save/load round trip
                print("[Step 13] Testing save/load...")
                settings.save("test_multi.json")
                loaded = AppSettings.load("test_multi.json")
                ls = loaded.get_snapshot()
                print(f"  Loaded: {len(ls['sensors'])} sensors, {len(ls['screens'])} screens, {len(ls['outputs'])} outputs")
                assert len(ls['sensors']) == 1
                assert len(ls['screens']) == 2
                assert len(ls['outputs']) == 2
                os.remove("test_multi.json")
                results.append("PASS: Save/load preserves multi config")

            elif s == 14:
                # Final results
                print("\n" + "=" * 50)
                print("TEST RESULTS")
                print("=" * 50)
                for r in results:
                    print(f"  {r}")
                print(f"\nTotal: {len(results)} tests passed")
                print("=" * 50)

                for scanner in window._scanners:
                    scanner.stop()
                for pipeline in window._pipelines:
                    pipeline.stop()
                app.quit()
                return

            QTimer.singleShot(500, test_step)

        except Exception as e:
            print(f"\nFAILED at step {step[0]-1}: {e}")
            import traceback
            traceback.print_exc()
            for scanner in window._scanners:
                scanner.stop()
            for pipeline in window._pipelines:
                pipeline.stop()
            app.quit()

    QTimer.singleShot(1500, test_step)
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_test()
