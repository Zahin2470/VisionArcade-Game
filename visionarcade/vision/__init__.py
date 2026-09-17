"""Vision layer: camera capture, hand tracking, and (in later phases)
gesture/motion recognition and calibration.

The rest of the application never talks to OpenCV or MediaPipe directly —
it consumes the stabilized, normalized signals this package produces.
"""
