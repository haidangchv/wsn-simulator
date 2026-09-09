import pandas as pd


class EnvironmentalDataCollector:
    """
    Store environmental measurements generated
    by sensors and measurements successfully
    received at the Sink.
    """

    def __init__(self):

        self.generated_records = []

        self.received_records = []

    @staticmethod
    def _packet_record(
        packet,
        sensor
    ) -> dict:

        return {
            "source_id":
                packet.source_id,

            "sensor_type":
                packet.sensor_type,

            "round":
                packet.created_round,

            "simulation_time_seconds":
                packet.simulation_time_seconds,

            "value":
                packet.measurement_value,

            "unit":
                packet.measurement_unit,

            "x":
                sensor.x,

            "y":
                sensor.y,

            "payload_size_bytes":
                packet.payload_size_bytes
        }

    def record_generated(
        self,
        packet,
        sensor
    ) -> None:

        if (
            packet.measurement_value
            is None
        ):
            return

        record = (
            self._packet_record(
                packet,
                sensor
            )
        )

        self.generated_records.append(
            record
        )

    def record_received(
        self,
        packet,
        sensor
    ) -> None:

        if not packet.delivered:
            return

        if (
            packet.measurement_value
            is None
        ):
            return

        record = (
            self._packet_record(
                packet,
                sensor
            )
        )

        record[
            "hop_count"
        ] = packet.hop_count

        record[
            "delay_ms"
        ] = packet.delay_ms

        self.received_records.append(
            record
        )

    def generated_dataframe(
        self
    ) -> pd.DataFrame:

        return pd.DataFrame(
            self.generated_records
        )

    def received_dataframe(
        self
    ) -> pd.DataFrame:

        return pd.DataFrame(
            self.received_records
        )

    def latest_received_dataframe(
        self
    ) -> pd.DataFrame:

        dataframe = (
            self.received_dataframe()
        )

        if dataframe.empty:
            return dataframe

        dataframe = (
            dataframe
            .sort_values(
                "round"
            )
        )

        return (
            dataframe
            .groupby(
                "source_id",
                as_index=False
            )
            .tail(1)
            .reset_index(
                drop=True
            )
        )

    def type_dataframe(
        self,
        sensor_type: str
    ) -> pd.DataFrame:

        dataframe = (
            self.received_dataframe()
        )

        if dataframe.empty:
            return dataframe

        return (
            dataframe[
                dataframe[
                    "sensor_type"
                ]
                ==
                sensor_type
            ]
            .copy()
        )