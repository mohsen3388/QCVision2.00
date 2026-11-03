from __future__ import annotations

from dataclasses import dataclass

from visionqc.domain.events import DomainEvent
from visionqc.platform.container import ServiceContainer
from visionqc.platform.event_bus import InProcessEventBus
from visionqc.plugins.base import PluginMetadata, VisionQCPlugin


def test_event_bus_delivers_named_and_wildcard_events():
    bus = InProcessEventBus()
    received = []
    bus.subscribe("inspection.completed", received.append)
    bus.subscribe("*", received.append)
    event = DomainEvent("inspection.completed", {"passed": True})
    bus.publish(event)
    assert received == [event, event]


def test_event_bus_unsubscribe():
    bus = InProcessEventBus()
    received = []
    bus.subscribe("x", received.append)
    bus.unsubscribe("x", received.append)
    bus.publish(DomainEvent("x"))
    assert received == []


def test_container_supports_instances_and_factories():
    container = ServiceContainer()
    container.register_instance("answer", 42)
    container.register_factory("double", lambda c: c.resolve("answer") * 2)
    assert container.resolve("answer") == 42
    assert container.resolve("double") == 84


def test_plugin_contract_can_register_services():
    class TestPlugin(VisionQCPlugin):
        metadata = PluginMetadata("test", "Test", "1.0")
        def register(self, container: ServiceContainer) -> None:
            container.register_instance("plugin_value", "ready")

    container = ServiceContainer()
    TestPlugin().register(container)
    assert container.resolve("plugin_value") == "ready"
