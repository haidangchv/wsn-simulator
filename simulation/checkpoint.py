from __future__ import annotations

from datetime import datetime
import gzip
import hashlib
import io
from pathlib import Path
import pickle
import random
from typing import Any

import numpy as np


CHECKPOINT_MAGIC = "WSN_SIMULATOR_CHECKPOINT"

# Tăng số này nếu sau này thay đổi cấu trúc checkpoint.
CHECKPOINT_SCHEMA_VERSION = 1


class CheckpointError(Exception):
    pass


def _payload_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_checkpoint_boundary(
    simulator
) -> None:
    """
    Đảm bảo checkpoint chỉ được lưu ở ranh giới giữa hai round hoàn chỉnh,
    không lưu khi một round đang xử lý dở dang.
    """
    if getattr(
        simulator,
        "round_in_progress",
        False
    ):
        raise CheckpointError(
            "Không thể lưu checkpoint khi một round đang chạy."
        )


def create_checkpoint_bytes(
    simulator,
    config: dict,
    app_version: str = "1.0"
) -> bytes:
    """
    Serialize toàn bộ trạng thái simulation thành định dạng nén Gzip.

    Chỉ nên gọi sau khi một round đã hoàn tất.
    """
    validate_checkpoint_boundary(
        simulator
    )

    checkpoint = {
        "magic":
            CHECKPOINT_MAGIC,

        "schema_version":
            CHECKPOINT_SCHEMA_VERSION,

        "app_version":
            app_version,

        "created_at":
            datetime.now().isoformat(
                timespec="seconds"
            ),

        "round":
            simulator.current_round,

        "config":
            config,

        # Quan trọng nhất:
        # lưu nguyên simulator thay vì chỉ lưu một vài metric.
        "simulator":
            simulator,

        # RNG global - phòng trường hợp một module
        # cũ vẫn sử dụng random / np.random.
        "python_random_state":
            random.getstate(),

        "numpy_random_state":
            np.random.get_state(),
    }

    raw_payload = pickle.dumps(
        checkpoint,
        protocol=pickle.HIGHEST_PROTOCOL
    )

    wrapper = {
        "sha256":
            _payload_hash(
                raw_payload
            ),

        "payload":
            raw_payload
    }

    buffer = io.BytesIO()

    with gzip.GzipFile(
        fileobj=buffer,
        mode="wb",
        compresslevel=6
    ) as gz:

        pickle.dump(
            wrapper,
            gz,
            protocol=pickle.HIGHEST_PROTOCOL
        )

    return buffer.getvalue()


def restore_checkpoint_bytes(
    data: bytes
) -> dict[str, Any]:
    """
    Khôi phục checkpoint từ chuỗi bytes.
    Kiểm tra tính toàn vẹn (integrity), magic header, version,
    và khôi phục RNG state.
    """
    try:
        buffer = io.BytesIO(
            data
        )

        with gzip.GzipFile(
            fileobj=buffer,
            mode="rb"
        ) as gz:

            wrapper = pickle.load(
                gz
            )

    except Exception as exc:
        raise CheckpointError(
            "Không thể đọc checkpoint."
        ) from exc

    if (
        not isinstance(
            wrapper,
            dict
        )
        or
        "payload"
        not in wrapper
    ):
        raise CheckpointError(
            "Checkpoint không hợp lệ."
        )

    raw_payload = (
        wrapper["payload"]
    )

    expected_hash = (
        wrapper.get(
            "sha256"
        )
    )

    actual_hash = (
        _payload_hash(
            raw_payload
        )
    )

    if (
        expected_hash
        !=
        actual_hash
    ):
        raise CheckpointError(
            "Checkpoint bị lỗi hoặc đã bị thay đổi (SHA256 mismatch)."
        )

    try:
        checkpoint = pickle.loads(
            raw_payload
        )

    except Exception as exc:
        raise CheckpointError(
            "Không thể khôi phục trạng thái mô phỏng."
        ) from exc

    if (
        checkpoint.get(
            "magic"
        )
        !=
        CHECKPOINT_MAGIC
    ):
        raise CheckpointError(
            "Đây không phải checkpoint của WSN Simulator."
        )

    if (
        checkpoint.get(
            "schema_version"
        )
        !=
        CHECKPOINT_SCHEMA_VERSION
    ):
        raise CheckpointError(
            "Phiên bản checkpoint không tương thích."
        )

    # Khôi phục RNG global
    if "python_random_state" in checkpoint:
        random.setstate(
            checkpoint[
                "python_random_state"
            ]
        )

    if "numpy_random_state" in checkpoint:
        np.random.set_state(
            checkpoint[
                "numpy_random_state"
            ]
        )

    return checkpoint


def save_checkpoint_file(
    simulator,
    config: dict,
    path: str | Path,
    app_version: str = "1.0"
) -> Path:
    """
    Lưu checkpoint vào file với cơ chế atomic replacement
    để tránh hỏng file nếu quá trình ghi bị ngắt đột ngột.
    """
    data = create_checkpoint_bytes(
        simulator=simulator,
        config=config,
        app_version=app_version
    )

    path = Path(
        path
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_path = (
        path.with_suffix(
            path.suffix + ".tmp"
        )
    )

    temporary_path.write_bytes(
        data
    )

    # Atomic-ish replacement: tránh file checkpoint dở dang nếu ngắt điện / crash
    temporary_path.replace(
        path
    )

    return path


def auto_checkpoint(
    simulator,
    config: dict,
    checkpoint_config: dict,
    app_version: str = "1.0"
) -> Path | None:
    """
    Thực hiện auto-save định kỳ theo cấu hình `checkpoint`.
    Hỗ trợ quay vòng (rotate) giữ lại tối đa `keep_last` checkpoint gần nhất.
    """
    if not checkpoint_config.get(
        "auto_save",
        False
    ):
        return None

    interval = int(
        checkpoint_config.get(
            "interval_rounds",
            500
        )
    )

    if interval <= 0:
        return None

    if (
        simulator.current_round <= 0
        or
        simulator.current_round % interval != 0
    ):
        return None

    directory = Path(
        checkpoint_config.get(
            "directory",
            "checkpoints"
        )
    )

    directory.mkdir(
        parents=True,
        exist_ok=True
    )

    filename = (
        f"checkpoint_"
        f"{simulator.current_round:08d}"
        ".wsnchk.gz"
    )

    path = (
        directory
        /
        filename
    )

    save_checkpoint_file(
        simulator=simulator,
        config=config,
        path=path,
        app_version=app_version
    )

    keep_last = int(
        checkpoint_config.get(
            "keep_last",
            3
        )
    )

    if keep_last > 0:
        files = sorted(
            directory.glob(
                "checkpoint_*.wsnchk.gz"
            )
        )

        old_files = files[:-keep_last]

        for old_file in old_files:
            try:
                old_file.unlink()
            except OSError:
                pass

    return path
