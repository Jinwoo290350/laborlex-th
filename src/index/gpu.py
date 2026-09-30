"""One process-wide lock for every model on the MPS/GPU device.

bge-m3 (embedding) and bge-reranker share the Metal command queue; separate locks still
let two threads encode at once and crash Metal ("failed assertion _status <
MTLCommandBufferStatusCommitted"). All device work goes through this lock."""

import threading

DEVICE_LOCK = threading.RLock()
