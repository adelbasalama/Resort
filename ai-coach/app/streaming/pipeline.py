"""Small event stream framework demonstrating ABCs, composition and generators."""
from abc import ABC, abstractmethod


class StreamProcessor(ABC):
    @abstractmethod
    def process(self, event):
        """Return a transformed event or None to discard it."""

    def __or__(self, other):
        return Pipeline(self, other)

    def __add__(self, other):
        return self.__or__(other)


class Pipeline(StreamProcessor):
    def __init__(self, *processors):
        self.processors = []
        for processor in processors:
            self.processors.extend(processor.processors if isinstance(processor, Pipeline) else [processor])

    def process(self, event):
        current = event
        for processor in self.processors:
            if current is None: break
            current = processor.process(current)
        return current

    def __or__(self, other):
        return Pipeline(self, other)

    def __add__(self, other):
        return self.__or__(other)


class FilterProcessor(StreamProcessor):
    def __init__(self, predicate): self.predicate = predicate
    def process(self, event): return event if self.predicate(event) else None


class MapProcessor(StreamProcessor):
    def __init__(self, transform): self.transform = transform
    def process(self, event): return self.transform(event)


class EventStream:
    def __init__(self, events, pipeline):
        self._events = iter(events)
        self.pipeline = pipeline
    def __iter__(self): return self
    def __next__(self):
        for event in self._events:
            result = self.pipeline.process(event)
            if result is not None: return result
        raise StopIteration
    def consume(self):
        yield from self
