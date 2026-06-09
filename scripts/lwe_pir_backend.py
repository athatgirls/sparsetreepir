from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Dict, List, Optional, Sequence

import numpy as np


MODULUS_BITS = 32
MODULUS = 1 << MODULUS_BITS
MASK = np.uint64(MODULUS - 1)
PLAINTEXT_MODULUS = 256
SCALE = MODULUS // PLAINTEXT_MODULUS
COEFF_BYTES = MODULUS_BITS // 8
RECORD_BYTES = 32


@dataclass
class LwePirTable:
    data: np.ndarray
    public_matrix: np.ndarray
    hint: np.ndarray
    setup_ms: float


def random_byte_database(subdatabase_sizes: Sequence[int], seed: int) -> List[np.ndarray]:
    rng = np.random.default_rng(seed)
    tables: List[np.ndarray] = []
    for size in subdatabase_sizes:
        padded_size = max(1, int(size))
        table = rng.integers(0, PLAINTEXT_MODULUS, size=(padded_size, RECORD_BYTES), dtype=np.uint8)
        if size <= 0:
            table[0] = 0
        tables.append(table)
    return tables


def _mod32(matrix: np.ndarray) -> np.ndarray:
    return np.bitwise_and(matrix.astype(np.uint64, copy=False), MASK)


def setup_lwe_pir_database(
    tables: Sequence[np.ndarray],
    seed: int,
    dimension: int = 64,
) -> List[LwePirTable]:
    rng = np.random.default_rng(seed)
    prepared: List[LwePirTable] = []
    for table in tables:
        data = table.astype(np.uint64, copy=False)
        rows = int(data.shape[0])
        public_matrix = rng.integers(0, MODULUS, size=(rows, dimension), dtype=np.uint64)

        t0 = perf_counter()
        hint = _mod32(data.T @ public_matrix)
        t1 = perf_counter()

        prepared.append(
            LwePirTable(
                data=data,
                public_matrix=public_matrix,
                hint=hint,
                setup_ms=(t1 - t0) * 1000.0,
            )
        )
    return prepared


def _noise_mod(noise: np.ndarray) -> np.ndarray:
    encoded = np.zeros(noise.shape, dtype=np.uint64)
    encoded[noise > 0] = 1
    encoded[noise < 0] = MODULUS - 1
    return encoded


def execute_lwe_batch_pir(
    database: Sequence[LwePirTable],
    targets: Sequence[Optional[int]],
    seed: int,
) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    query_bytes = 0
    response_bytes = 0
    hint_bytes = 0
    setup_ms = 0.0
    query_time = 0.0
    extract_time = 0.0
    server_total = 0.0
    server_parallel = 0.0

    for table_index, (table, target) in enumerate(zip(database, targets)):
        rows = int(table.data.shape[0])
        dimension = int(table.public_matrix.shape[1])
        chosen = int(rng.integers(0, rows)) if target is None else int(target)
        if chosen < 0 or chosen >= rows:
            raise IndexError(f"LWE-PIR target {chosen} out of range for table {table_index} of size {rows}.")

        setup_ms += table.setup_ms
        hint_bytes += table.hint.size * COEFF_BYTES

        t0 = perf_counter()
        secret = rng.integers(0, MODULUS, size=dimension, dtype=np.uint64)
        error = rng.integers(-1, 2, size=rows, dtype=np.int16)
        query = _mod32(table.public_matrix @ secret)
        query = _mod32(query + _noise_mod(error))
        query[chosen] = np.uint64((int(query[chosen]) + SCALE) & int(MASK))
        t1 = perf_counter()
        query_time += t1 - t0

        s0 = perf_counter()
        response = _mod32(table.data.T @ query)
        s1 = perf_counter()
        current_server = s1 - s0
        server_total += current_server
        server_parallel = max(server_parallel, current_server)

        e0 = perf_counter()
        hint_secret = _mod32(table.hint @ secret)
        noisy_scaled = _mod32(response - hint_secret)
        decoded = ((noisy_scaled + (SCALE // 2)) // SCALE).astype(np.uint64) % PLAINTEXT_MODULUS
        recovered = decoded.astype(np.uint8)
        expected = table.data[chosen].astype(np.uint8)
        if not np.array_equal(recovered, expected):
            raise RuntimeError("LWE-PIR prototype failed to decode the selected record.")
        e1 = perf_counter()
        extract_time += e1 - e0

        query_bytes += rows * COEFF_BYTES
        response_bytes += RECORD_BYTES * COEFF_BYTES

    return {
        "query_bytes": float(query_bytes),
        "response_bytes": float(response_bytes),
        "hint_bytes": float(hint_bytes),
        "setup_ms": float(setup_ms),
        "client_query_ms": query_time * 1000.0,
        "client_extract_ms": extract_time * 1000.0,
        "server_total_ms": server_total * 1000.0,
        "server_parallel_ms": server_parallel * 1000.0,
    }


def average_lwe_metrics(samples: Sequence[Dict[str, float]]) -> Dict[str, float]:
    if not samples:
        return {
            "query_bytes": 0.0,
            "response_bytes": 0.0,
            "hint_bytes": 0.0,
            "setup_ms": 0.0,
            "client_query_ms": 0.0,
            "client_extract_ms": 0.0,
            "server_total_ms": 0.0,
            "server_parallel_ms": 0.0,
        }
    return {
        key: sum(sample[key] for sample in samples) / len(samples)
        for key in samples[0]
    }
