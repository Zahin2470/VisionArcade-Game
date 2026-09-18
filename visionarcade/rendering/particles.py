"""A small, reusable particle system for hit/catch feedback bursts.

Shared across mini-games rather than each one drawing its own ad hoc
sparks. Visual randomness is injected via a `random.Random` instance
so tests can seed it for fully deterministic assertions.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame

Color = Tuple[int, int, int]

_GRAVITY = 220.0  # px/sec^2, a gentle arc rather than a straight fade-out


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: Color
    radius: float


class ParticleSystem:
    """A simple, capped set of short-lived particles."""

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self._rng = rng if rng is not None else random.Random()
        self._particles: List[Particle] = []

    @property
    def count(self) -> int:
        return len(self._particles)

    def burst(
        self,
        x: float,
        y: float,
        color: Color,
        count: int = 16,
        speed_range: Tuple[float, float] = (60.0, 180.0),
        life_range: Tuple[float, float] = (0.3, 0.7),
        radius_range: Tuple[float, float] = (2.0, 5.0),
    ) -> None:
        """Spawn `count` particles radiating outward from (x, y)."""
        for _ in range(count):
            angle = self._rng.uniform(0.0, 2.0 * math.pi)
            speed = self._rng.uniform(*speed_range)
            vx, vy = math.cos(angle) * speed, math.sin(angle) * speed
            life = self._rng.uniform(*life_range)
            radius = self._rng.uniform(*radius_range)
            self._particles.append(Particle(x, y, vx, vy, life, life, color, radius))

    def update(self, dt: float) -> None:
        alive: List[Particle] = []
        for particle in self._particles:
            particle.life -= dt
            if particle.life > 0:
                particle.x += particle.vx * dt
                particle.y += particle.vy * dt
                particle.vy += _GRAVITY * dt
                alive.append(particle)
        self._particles = alive

    def draw(self, surface: pygame.Surface) -> None:
        for particle in self._particles:
            fraction = max(0.0, particle.life / particle.max_life)
            radius = max(1, int(particle.radius * fraction))
            pygame.draw.circle(surface, particle.color, (int(particle.x), int(particle.y)), radius)

    def clear(self) -> None:
        self._particles.clear()
