# Robust Realtime Attendance Architecture Plan

## Problem Analysis
Despite previous optimizations (batch processing and caching), users still report missing attendance records. Investigation reveals several critical issues:

1.  **Thread Starvation (Single Pool)**: The `ZKRealtimeDeviceListener` uses a single `ThreadPoolExecutor` for all blocking operations. When many devices are connected, administrative tasks (connecting, fetching info) compete for threads with long-running listener loops.
2.  **Context Switching Overhead**: The `_live_capture_loop` uses an async generator pattern that yields control after every event or timeout. This causes the listener to lose its place in the thread pool queue, leading to gaps in monitoring.
3.  **Process-Bound Processing**: Although batching helps, the realtime listener process still handles DB writes and complex business logic (timesheet updates), which can block the event loop or consume CPU cycles needed for network I/O.

## Proposed Solution: Dedicated Listening & Async Processing

### 1. Dedicated Listener Threading Model
Refactor `ZKRealtimeDeviceListener` in `apps/devices/zk/listener.py`:
-   **Dual Thread Pools**:
    *   `_listener_executor`: A large pool (sized to `num_devices + buffer`) dedicated **strictly** to the `live_capture` loops.
    *   `_general_executor`: A separate pool for short-lived tasks (connect, disconnect, get_info, callbacks).
-   **Persistent Listening Threads**:
    *   Refactor `_live_capture_loop` to run as a continuous blocking loop inside a single thread.
    *   It will handle its own timeouts and heartbeat logic internally without exiting or yielding back to the main loop's executor.
    *   Events are pushed to the main loop using `asyncio.run_coroutine_threadsafe`.

### 2. Offloading to Celery (Async Business Logic)
Move the business logic out of the realtime process to ensure it remains lightweight and responsive:
-   **New Celery Task**: Create `process_realtime_attendance_event(event_data)` in `apps/hrm/tasks/attendances.py`.
    *   Handles DB lookups (Employee, Device).
    *   Duplicate detection.
    *   `AttendanceRecord` creation.
    *   Triggers `trigger_timesheet_updates_from_records`.
-   **Management Command Update**:
    *   Remove the internal `asyncio.Queue` and `save_batch` logic from `run_realtime_attendance_listener.py`.
    *   The command's only responsibility is to capture events and dispatch them to Celery: `task.delay(event_data)`.

### 3. Dynamic Scaling & Reliability
-   **Resource Monitoring**: The listener will calculate the required number of listener threads based on the number of enabled devices.
-   **Graceful Recovery**: Retain the exponential backoff for reconnection, but ensure that "checking online devices" doesn't disrupt active connections.

## Expected Outcomes
-   **Zero Gaps**: Continuous listening threads ensure no events are missed during context switches or task scheduling delays.
-   **Higher Capacity**: Can handle many more devices by isolating the monitoring from the processing logic.
-   **Process Resilience**: A crash in the DB or processing logic won't stop the listener process from capturing new events and queuing them in Redis/RabbitMQ.
