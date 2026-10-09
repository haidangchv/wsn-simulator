from collections import defaultdict, deque
import math


class HistoryDict(dict):
    """
    Dictionary that auto-initializes missing keys with a deque of given maxlen.
    Fully pickle-serializable (unlike a defaultdict with a lambda).
    """

    def __init__(self, maxlen: int = 20):
        super().__init__()
        self.maxlen = maxlen

    def __missing__(self, key):
        self[key] = deque(maxlen=self.maxlen)
        return self[key]


class RelayLoadTracker:
    """
    Theo dõi số packet mà mỗi sensor đã forward
    trong một cửa sổ các round gần nhất.

    Load factor:
        recent_forwarded_i / mean_recent_forwarded_active_relays

    Hysteresis:
        load >= overload_factor  -> overloaded
        load <= recovery_factor  -> recovered
    """

    def __init__(
        self,
        window_rounds: int = 20,
        overload_factor: float = 2.0,
        recovery_factor: float = 1.2
    ):

        if window_rounds <= 0:
            raise ValueError(
                "window_rounds must be > 0"
            )

        if recovery_factor >= overload_factor:
            raise ValueError(
                "recovery_factor must be "
                "smaller than overload_factor"
            )

        self.window_rounds = int(
            window_rounds
        )

        self.overload_factor = float(
            overload_factor
        )

        self.recovery_factor = float(
            recovery_factor
        )

        self.histories = HistoryDict(
            maxlen=self.window_rounds
        )

        self.last_forwarded_total = {}

        self.recent_forwarded = {}

        self.load_factors = {}

        self.overloaded_nodes = set()

    def reset(self):

        self.histories.clear()

        self.last_forwarded_total.clear()

        self.recent_forwarded.clear()

        self.load_factors.clear()

        self.overloaded_nodes.clear()

    def update(
        self,
        sensors
    ):
        """
        Gọi 1 lần ở đầu mỗi round.

        forwarded_packets là counter tích lũy.
        Ta lấy delta giữa 2 lần update để biết
        forwarding load của round vừa qua.
        """

        # ---------------------------------
        # Record forwarding from last round
        # ---------------------------------

        for sensor in sensors:

            node_id = sensor.node_id

            current_total = int(
                getattr(
                    sensor,
                    "forwarded_packets",
                    0
                )
            )

            if (
                node_id
                not in
                self.last_forwarded_total
            ):

                # Tracker được tạo giữa simulation
                # cũng không tạo một spike giả.
                previous_total = (
                    current_total
                )

            else:

                previous_total = (
                    self.last_forwarded_total[
                        node_id
                    ]
                )

            delta = max(
                0,
                current_total
                -
                previous_total
            )

            self.histories[
                node_id
            ].append(
                delta
            )

            self.last_forwarded_total[
                node_id
            ] = current_total

        # ---------------------------------
        # Recent forwarding count
        # ---------------------------------

        self.recent_forwarded = {
            node_id: sum(history)
            for node_id, history
            in self.histories.items()
        }

        # ---------------------------------
        # Average of active relays
        # ---------------------------------

        active_loads = []

        for sensor in sensors:

            if not sensor.is_alive():
                continue

            value = (
                self.recent_forwarded.get(
                    sensor.node_id,
                    0
                )
            )

            if value > 0:
                active_loads.append(
                    value
                )

        if active_loads:

            mean_active_load = (
                sum(active_loads)
                /
                len(active_loads)
            )

        else:

            mean_active_load = 1.0

        # ---------------------------------
        # Relative load
        # ---------------------------------

        self.load_factors = {}

        for sensor in sensors:

            node_id = sensor.node_id

            recent = (
                self.recent_forwarded.get(
                    node_id,
                    0
                )
            )

            self.load_factors[
                node_id
            ] = (
                recent
                /
                max(
                    mean_active_load,
                    1.0
                )
            )

        # ---------------------------------
        # Hysteresis overload state
        # ---------------------------------

        for sensor in sensors:

            node_id = sensor.node_id

            if not sensor.is_alive():

                self.overloaded_nodes.discard(
                    node_id
                )

                continue

            load_factor = (
                self.load_factors.get(
                    node_id,
                    0.0
                )
            )

            if (
                node_id
                in
                self.overloaded_nodes
            ):

                # Chỉ phục hồi khi tải giảm
                # đủ thấp.
                if (
                    load_factor
                    <=
                    self.recovery_factor
                ):

                    self.overloaded_nodes.discard(
                        node_id
                    )

            else:

                if (
                    load_factor
                    >=
                    self.overload_factor
                ):

                    self.overloaded_nodes.add(
                        node_id
                    )

    def get_load_factor(
        self,
        node_id
    ) -> float:

        return float(
            self.load_factors.get(
                node_id,
                0.0
            )
        )

    def get_recent_forwarded(
        self,
        node_id
    ) -> int:

        return int(
            self.recent_forwarded.get(
                node_id,
                0
            )
        )

    def is_overloaded(
        self,
        node_id
    ) -> bool:

        return (
            node_id
            in
            self.overloaded_nodes
        )

    def get_metrics(
        self
    ) -> dict:

        active_loads = [
            value
            for value
            in self.recent_forwarded.values()
            if value > 0
        ]

        if not active_loads:

            return {
                "overloaded_relay_count":
                    len(
                        self.overloaded_nodes
                    ),

                "active_relay_count":
                    0,

                "mean_relay_load":
                    0.0,

                "max_relay_load":
                    0,

                "relay_load_cv":
                    0.0
            }

        mean_value = (
            sum(active_loads)
            /
            len(active_loads)
        )

        variance = (
            sum(
                (
                    value
                    -
                    mean_value
                ) ** 2

                for value
                in active_loads
            )
            /
            len(active_loads)
        )

        std_value = math.sqrt(
            variance
        )

        cv = (
            std_value
            /
            mean_value
            if mean_value > 0
            else 0.0
        )

        return {
            "overloaded_relay_count":
                len(
                    self.overloaded_nodes
                ),

            "active_relay_count":
                len(
                    active_loads
                ),

            "mean_relay_load":
                mean_value,

            "max_relay_load":
                max(
                    active_loads
                ),

            "relay_load_cv":
                cv
        }
