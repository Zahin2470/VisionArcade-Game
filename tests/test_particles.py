"""Tests for `visionarcade.rendering.particles.ParticleSystem`."""

from __future__ import annotations

import random

from visionarcade.rendering.particles import ParticleSystem


def test_no_particles_initially():
    system = ParticleSystem(rng=random.Random(1))
    assert system.count == 0


def test_burst_adds_requested_count():
    system = ParticleSystem(rng=random.Random(1))
    system.burst(10, 10, (255, 0, 0), count=12)
    assert system.count == 12


def test_multiple_bursts_accumulate():
    system = ParticleSystem(rng=random.Random(1))
    system.burst(0, 0, (255, 0, 0), count=5)
    system.burst(0, 0, (0, 255, 0), count=5)
    assert system.count == 10


def test_particles_move_over_time():
    system = ParticleSystem(rng=random.Random(1))
    system.burst(0, 0, (255, 0, 0), count=1, speed_range=(100, 100), life_range=(1.0, 1.0))
    x0, y0 = system._particles[0].x, system._particles[0].y
    system.update(0.1)
    x1, y1 = system._particles[0].x, system._particles[0].y
    assert (x0, y0) != (x1, y1)


def test_particles_die_after_their_lifetime():
    system = ParticleSystem(rng=random.Random(1))
    system.burst(0, 0, (255, 0, 0), count=5, life_range=(0.1, 0.1))
    system.update(0.2)  # longer than the particles' life
    assert system.count == 0


def test_short_update_keeps_particles_alive():
    system = ParticleSystem(rng=random.Random(1))
    system.burst(0, 0, (255, 0, 0), count=5, life_range=(1.0, 1.0))
    system.update(0.1)
    assert system.count == 5


def test_clear_removes_all_particles():
    system = ParticleSystem(rng=random.Random(1))
    system.burst(0, 0, (255, 0, 0), count=5)
    system.clear()
    assert system.count == 0


def test_draw_does_not_raise(renderer):
    system = ParticleSystem(rng=random.Random(1))
    system.burst(50, 50, (255, 0, 0), count=10)
    system.draw(renderer.surface)  # must not raise


def test_seeded_rng_is_reproducible():
    system_a = ParticleSystem(rng=random.Random(42))
    system_b = ParticleSystem(rng=random.Random(42))
    system_a.burst(0, 0, (255, 0, 0), count=3)
    system_b.burst(0, 0, (255, 0, 0), count=3)
    positions_a = [(p.vx, p.vy) for p in system_a._particles]
    positions_b = [(p.vx, p.vy) for p in system_b._particles]
    assert positions_a == positions_b
