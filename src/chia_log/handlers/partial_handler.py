# std
from typing import List, Optional

# project
from . import LogHandlerInterface
from ..parsers.partial_parser import PartialParser
from .condition_checkers import PartialConditionChecker
from .daily_stats.stats_manager import StatsManager
from src.notifier import Event


class PartialHandler(LogHandlerInterface):
    """This handler parses all logs indicating found partials
    activity by the full node. It holds a list of condition checkers
    that are evaluated for each event.
    """

    @staticmethod
    def config_name() -> str:
        return "partial_handler"

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._parser = PartialParser(config)
        self._cond_checkers: List[PartialConditionChecker] = []

    def handle(self, logs: str, stats_manager: Optional[StatsManager] = None) -> List[Event]:
        """Process incoming logs, check all conditions
        and return a list of notable events.
        """

        events = []
        activity_messages = self._parser.parse(logs)
        if stats_manager:
            stats_manager.consume_partial_messages(activity_messages)

        # Run messages through all condition checkers
        for msg in activity_messages:
            for checker in self._cond_checkers:
                event = checker.check(msg)
                if event:
                    events.append(event)

        return events
