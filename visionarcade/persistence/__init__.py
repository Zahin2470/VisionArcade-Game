"""Local persistence: user settings, high scores, and player profiles.

Implemented in Phase 3. Must never let one malformed/corrupted record
break the entire save file - each module here isolates and recovers
from partial corruption rather than discarding all saved data.
"""
