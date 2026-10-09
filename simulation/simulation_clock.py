from datetime import datetime, timedelta


class SimulationClock:
    """
    Simulation time manager converting rounds to timestamps,
    elapsed seconds, days, and simulation calendar dates.
    Default: 1 round = 1 hour (60 minutes).
    """

    def __init__(self, config: dict):

        time_config = (
            config
            .get("simulation", {})
            .get("time", {})
        )

        self.start_datetime = (
            datetime.fromisoformat(
                time_config.get(
                    "start_datetime",
                    "2026-01-01 00:00:00"
                )
            )
        )

        if "round_duration_minutes" in time_config:
            self.round_duration_minutes = int(
                time_config["round_duration_minutes"]
            )
            self._round_duration_seconds = (
                self.round_duration_minutes * 60
            )
        elif (
            "packet" in config
            and "sampling_interval_seconds" in config["packet"]
        ):
            self._round_duration_seconds = int(
                config["packet"]["sampling_interval_seconds"]
            )
            self.round_duration_minutes = max(
                1,
                self._round_duration_seconds // 60
            )
        else:
            self.round_duration_minutes = 60
            self._round_duration_seconds = 3600

    @property
    def round_duration_seconds(self) -> int:

        return int(
            self._round_duration_seconds
        )

    @property
    def rounds_per_day(self) -> int:

        return int(
            (24 * 60)
            /
            self.round_duration_minutes
        )

    def datetime_for_round(
        self,
        round_number: int
    ) -> datetime:
        """
        Round 1 corresponds to start_datetime (00:00).
        Round 2 corresponds to +1 hour (01:00), etc.
        """
        effective_round = max(round_number, 1)
        return (
            self.start_datetime
            +
            timedelta(
                minutes=(
                    (effective_round - 1)
                    *
                    self.round_duration_minutes
                )
            )
        )

    def elapsed_seconds(
        self,
        round_number: int
    ) -> float:

        return (
            round_number
            *
            self.round_duration_seconds
        )

    def elapsed_days(
        self,
        round_number: int
    ) -> float:

        return (
            round_number
            /
            self.rounds_per_day
        )


def duration_to_rounds(
    value: int,
    unit: str,
    rounds_per_day: int
) -> int:
    """
    Convert simulation duration into round count.
    """
    if unit == "Rounds":
        return int(value)

    if unit == "Days":
        return int(value * rounds_per_day)

    if unit == "Weeks":
        return int(value * 7 * rounds_per_day)

    if unit == "Months":
        # 30 days/month simulation duration estimate
        return int(value * 30 * rounds_per_day)

    raise ValueError(f"Unknown unit: {unit}")


def round_to_days(
    round_number: int | None,
    rounds_per_day: int = 24
) -> float | None:
    """
    Convert round number into simulation days. Default: 24 rounds/day.
    """
    if round_number is None:
        return None

    return round_number / max(rounds_per_day, 1)
