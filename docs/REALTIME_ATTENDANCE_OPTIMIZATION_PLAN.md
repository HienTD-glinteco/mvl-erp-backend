# Optimization Plan for Realtime Attendance Listener

## Problem Analysis
The current implementation of `run_realtime_attendance_listener` suffers from significant performance bottlenecks when handling high volumes of events from multiple devices:
1.  **Synchronous Blocking I/O**: The `handle_attendance_event` callback executes synchronous Django ORM operations (DB reads/writes).
2.  **Thread Pool Saturation**: The listener wraps these synchronous callbacks in `asyncio.to_thread`. With thousands of events, this exhausts the thread pool or causes excessive context switching.
3.  **N+1 Queries**: For *each* event, the system performs a query to fetch the Device and another to fetch the Employee.
4.  **Single Row Inserts**: Each event results in a separate `AttendanceRecord.objects.create()` call, which is inefficient for high throughput.

## Proposed Solution
We will refactor the command to use a **Producer-Consumer** pattern with **Batch Processing** and **Caching**.

### 1. Producer-Consumer Architecture
-   **Producer**: The `handle_attendance_event` callback (running in a thread) will simply push the event data into an `asyncio.Queue`. This operation is near-instant, freeing up the listener's thread immediately.
-   **Consumer**: A dedicated background task (running in the main asyncio loop) will read events from the queue and process them.

### 2. Batch Processing
The consumer task will process events in batches (e.g., every 100 events or every 1 second, whichever comes first).
-   **Bulk Read**: Fetch all required `AttendanceDevice` and `Employee` records for the entire batch in minimal queries.
-   **Bulk Write**: Use `AttendanceRecord.objects.bulk_create()` to insert all records in a single transaction.

### 3. Caching
-   **Devices**: Cache `AttendanceDevice` objects in memory (id -> object). Since devices rarely change, this eliminates one DB query per event.
-   **Employees**: Cache `Employee` objects (attendance_code -> id). This eliminates the employee lookup query.

### 4. Implementation Details
-   Refactor the module-level callback functions into methods of the `Command` class to share state (queue, loop, caches).
-   Use `loop.call_soon_threadsafe` to push to the async queue from the threaded callback.
-   Implement a graceful shutdown mechanism that ensures the queue is drained before exiting.

## Implementation Status (Completed)

### ✅ Producer-Consumer Architecture
-   The `Command` class now initializes an `asyncio.Queue`.
-   `ZKRealtimeDeviceListener` was updated to support **async callbacks**, avoiding `asyncio.to_thread` overhead for the producer.
-   `on_attendance_event` is now an `async` function that directly pushes events to the queue (`self.queue.put_nowait(event)`).

### ✅ Batch Processing
-   `process_events` background task implements batch processing (100 events or 1 second timeout).
-   `save_batch` handles bulk insertion using `AttendanceRecord.objects.bulk_create`.

### ✅ Caching
-   `device_cache` stores `AttendanceDevice` objects to avoid repetitive DB lookups.
-   `employee_cache` stores mapping of `attendance_code` to `employee_id`.
-   Employees are bulk fetched based on attendance codes in the current batch.

### ✅ Graceful Shutdown
-   Signal handlers (SIGINT, SIGTERM) set `self.running = False`.
-   `process_events` task ensures remaining items in the queue are saved on cancellation.
-   `drain_queue` method explicitly drains and saves any pending events when the listener stops.

### ✅ Thread Pool Optimization for Blocking I/O
-   The `ZKRealtimeDeviceListener` now uses a dedicated `concurrent.futures.ThreadPoolExecutor` for all blocking operations (device connections, `live_capture` loops, and synchronous callbacks).
-   This ensures that the main asyncio loop and its default executor are not starved, significantly improving scalability for a large number of concurrent device connections.
-   The `max_workers` parameter can be configured to control the size of this dedicated thread pool.

## Robust Realtime Attendance Architecture (Recommended Follow-up)

## Problem Summary
Despite the batch processing and caching improvements above, operational experience shows missing attendance records and reliability issues when scaling to many devices. Root causes include:

- Thread pool contention between long-running listener loops and short-lived admin tasks.
- Listener loops that yield frequently cause scheduling gaps and lost events under heavy load.
- Processing and business logic (DB writes, timesheet updates) still run in the same process, so failures there can impact event capture.

## Key Recommendations

1.  Dedicated Listening & Threading Model
	- Dual thread pools:
		* `_listener_executor`: sized to `num_devices + buffer`, dedicated strictly to persistent `live_capture` loops.
		* `_general_executor`: separate pool for short-lived operations (connect, disconnect, get_info, callbacks).
	- Persist listening threads:
		* Refactor each `_live_capture_loop` to run as a continuous blocking loop inside a single thread, managing its own timeouts and heartbeat logic without exiting on each yield.
		* Use `asyncio.run_coroutine_threadsafe` or `loop.call_soon_threadsafe` to push events to the main process without repeatedly reacquiring executor threads.

2.  Offload Business Logic to Celery
	- Create a new Celery task `process_realtime_attendance_event(event_data)` in `apps/hrm/tasks/attendances.py` that encapsulates:
		* Employee and Device lookups, duplicate detection, `AttendanceRecord` creation, and subsequent timesheet triggers.
	- The realtime listener's responsibility becomes lightweight: capture events and enqueue them to Celery (e.g., `process_realtime_attendance_event.delay(event_data)`).
	- Benefits: listener remains responsive even if DB or processing tasks stall; Celery provides retry, visibility, and scaling.

3.  Reliability & Dynamic Scaling
	- Calculate and allocate `_listener_executor` size dynamically based on the number of enabled devices and a configurable buffer.
	- Maintain exponential backoff for connection retries but ensure health-check or administrative tasks do not use `_listener_executor` capacity needed for active listeners.
	- Implement health monitoring to detect stalled listeners and respawn threads without disrupting the global executor.

## Expected Outcomes

- Zero gaps in event capture due to persistent dedicated listener threads.
- Higher device capacity because listening is isolated from processing logic.
- Greater resilience: processing failures won't stop event collection; Celery ensures retries and persistence.

## Migration Options (phased)

- Blue/Green approach: Run the new listener process alongside the existing one; route a subset of devices to the new architecture to validate behavior at scale.
- Hybrid approach: Keep lightweight queue-and-batch processing for low-volume sites, and enable Celery-offload mode for high-volume deployments via a config flag.

## Next Steps

- Implement `_listener_executor` and `_general_executor` in `apps/devices/zk/listener.py`.
- Add `process_realtime_attendance_event` Celery task in `apps/hrm/tasks/attendances.py` and unit tests.
- Deploy in staging with a subset of devices; monitor for missed events and throughput.
