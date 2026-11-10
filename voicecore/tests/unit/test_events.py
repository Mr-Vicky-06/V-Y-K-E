import threading
import time
from voicecore.events import (
    Event,
    EventBus,
    ListeningStartedEvent,
    RouteEvent,
    GateEvent,
    DoneEvent,
)


def test_event_bus_subscribe_and_publish():
    bus = EventBus()
    received_routes = []

    def on_route(event: RouteEvent):
        received_routes.append(event)

    bus.subscribe(RouteEvent, on_route)

    event1 = RouteEvent(run_id="run1", calls=[{"name": "test"}], confidence=0.9)
    event2 = ListeningStartedEvent(run_id="run1")

    bus.publish(event1)
    bus.publish(event2)

    assert len(received_routes) == 1
    assert received_routes[0].confidence == 0.9
    assert received_routes[0].calls[0]["name"] == "test"


def test_event_bus_subscribe_all():
    bus = EventBus()
    all_events = []

    bus.subscribe_all(lambda e: all_events.append(e))

    bus.publish(ListeningStartedEvent(run_id="r1"))
    bus.publish(DoneEvent(run_id="r1", total_ms=50.0))

    assert len(all_events) == 2


def test_event_bus_unsubscribe():
    bus = EventBus()
    calls = []

    def handler(e):
        calls.append(e)

    bus.subscribe(DoneEvent, handler)
    bus.publish(DoneEvent(run_id="r1", total_ms=10.0))
    assert len(calls) == 1

    bus.unsubscribe(DoneEvent, handler)
    bus.publish(DoneEvent(run_id="r2", total_ms=20.0))
    assert len(calls) == 1


def test_event_bus_error_isolation():
    bus = EventBus()
    successful = []

    def failing_handler(e):
        raise RuntimeError("Handler blew up")

    def ok_handler(e):
        successful.append(e)

    bus.subscribe(DoneEvent, failing_handler)
    bus.subscribe(DoneEvent, ok_handler)

    # Should not raise exception
    bus.publish(DoneEvent(run_id="r1", total_ms=10.0))
    assert len(successful) == 1


def test_event_bus_thread_safety():
    bus = EventBus()
    received = []
    lock = threading.Lock()

    def collector(e):
        with lock:
            received.append(e)

    bus.subscribe_all(collector)

    threads = []
    for i in range(10):
        t = threading.Thread(target=lambda i=i: bus.publish(DoneEvent(run_id=f"r_{i}", total_ms=float(i))))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(received) == 10
