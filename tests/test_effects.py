"""Tests for `visionarcade.audio.effects`."""

from __future__ import annotations

from visionarcade.audio.effects import Sfx, SoundEffects
from visionarcade.audio.manager import AudioManager


def test_play_calls_audio_manager_with_the_mapped_path(monkeypatch):
    manager = AudioManager()
    calls = []
    monkeypatch.setattr(manager, "play_sfx", lambda path: calls.append(path))

    effects = SoundEffects(manager)
    effects.play(Sfx.SELECT)

    assert calls == ["audio/sfx/select.wav"]


def test_every_effect_has_a_mapped_path_and_does_not_raise():
    manager = AudioManager()
    effects = SoundEffects(manager)
    for effect in Sfx:
        effects.play(effect)  # missing assets degrade to silence, not an error
