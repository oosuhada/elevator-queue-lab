from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MotionProfile:
    """Symmetric triangular/trapezoidal point-to-point motion profile."""

    distance_m: float
    max_speed_mps: float
    acceleration_mps2: float
    peak_speed_mps: float
    accel_time_s: float
    cruise_time_s: float
    duration_s: float

    @classmethod
    def build(
        cls,
        distance_m: float,
        max_speed_mps: float,
        acceleration_mps2: float,
    ) -> "MotionProfile":
        if distance_m < 0:
            raise ValueError("distance_m must be non-negative")
        if max_speed_mps <= 0 or acceleration_mps2 <= 0:
            raise ValueError("speed and acceleration must be positive")
        if distance_m == 0:
            return cls(0.0, max_speed_mps, acceleration_mps2, 0.0, 0.0, 0.0, 0.0)

        distance_to_accelerate_and_brake = (max_speed_mps**2) / acceleration_mps2
        if distance_m <= distance_to_accelerate_and_brake:
            accel_time = math.sqrt(distance_m / acceleration_mps2)
            peak_speed = acceleration_mps2 * accel_time
            cruise_time = 0.0
        else:
            accel_time = max_speed_mps / acceleration_mps2
            peak_speed = max_speed_mps
            cruise_distance = distance_m - distance_to_accelerate_and_brake
            cruise_time = cruise_distance / max_speed_mps

        return cls(
            distance_m=distance_m,
            max_speed_mps=max_speed_mps,
            acceleration_mps2=acceleration_mps2,
            peak_speed_mps=peak_speed,
            accel_time_s=accel_time,
            cruise_time_s=cruise_time,
            duration_s=2 * accel_time + cruise_time,
        )

    def distance_at(self, elapsed_s: float) -> float:
        if self.distance_m == 0 or elapsed_s <= 0:
            return 0.0
        if elapsed_s >= self.duration_s:
            return self.distance_m

        a = self.acceleration_mps2
        t_accel = self.accel_time_s
        accel_distance = 0.5 * a * t_accel**2

        if elapsed_s <= t_accel:
            return 0.5 * a * elapsed_s**2

        cruise_end = t_accel + self.cruise_time_s
        if elapsed_s <= cruise_end:
            return accel_distance + self.peak_speed_mps * (elapsed_s - t_accel)

        decel_elapsed = elapsed_s - cruise_end
        cruise_distance = self.peak_speed_mps * self.cruise_time_s
        return (
            accel_distance
            + cruise_distance
            + self.peak_speed_mps * decel_elapsed
            - 0.5 * a * decel_elapsed**2
        )

    def fraction_at(self, elapsed_s: float) -> float:
        if self.distance_m == 0:
            return 1.0
        return min(1.0, max(0.0, self.distance_at(elapsed_s) / self.distance_m))


def service_dwell_seconds(
    transfer_count: int,
    base_dwell_seconds: float,
    seconds_per_transfer: float,
) -> float:
    if transfer_count < 0:
        raise ValueError("transfer_count cannot be negative")
    if base_dwell_seconds < 0 or seconds_per_transfer < 0:
        raise ValueError("dwell timing cannot be negative")
    return base_dwell_seconds + transfer_count * seconds_per_transfer

