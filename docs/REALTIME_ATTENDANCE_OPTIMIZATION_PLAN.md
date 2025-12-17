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
