"""Notifier package responsible for user notification

"""
import json
import logging
import re
import time
import traceback

# std
from abc import ABC, abstractmethod
from dataclasses import dataclass
from json_logic import jsonLogic
from typing import List
from enum import Enum

# Ignore Chiadog alerts about being offline due to entire container just launching in the first 30 minutes
MINIMUM_LAUNCH_SECONDS_BEFORE_ALERTING_ABOUT_BEING_OFFLINE = 30 * 60

class EventPriority(Enum):
    """Event priority dictates how urgently
    the user needs to be notified about it
    """

    LOW = -1
    NORMAL = 0
    HIGH = 1


class EventType(Enum):
    """Events can either be user events
    that are propagated directly to the
    user, or keep-alive events that are
    processed to ensure the system runs
    """

    KEEPALIVE = 0
    USER = 1
    DAILY_STATS = 2
    PLOTDECREASE = 3
    PLOTINCREASE = 4


class EventService(Enum):
    """Even service helps to distinguish
    between similar events for different services
    """

    HARVESTER = 0
    FARMER = 1
    FULL_NODE = 2
    DAILY = 3
    WALLET = 4


@dataclass
class Event:
    type: EventType
    priority: EventPriority
    service: EventService
    message: str


class Notifier(ABC):
    """This abstract class provides common interface for
    any notifier implementation. It should be easy to add
    extensions that integrate with variety of services such as
    Pushover, E-mail, Slack, WhatsApp, etc
    """

    def __init__(self, title_prefix: str, config: dict):
        self._program_launch_time = time.time()
        self._title_prefix = title_prefix
        self._config = config
        self._conn_timeout_seconds = 10
        self._notification_types = [EventType.USER]
        self._notification_services = [EventService.HARVESTER, EventService.FARMER, EventService.FULL_NODE]

        daily_stats = config.get("daily_stats", False)
        wallet_events = config.get("wallet_events", False)
        decreasing_plot_events = config.get("decreasing_plot_events", False)
        increasing_plot_events = config.get("increasing_plot_events", False)
        if daily_stats:
            self._notification_types.append(EventType.DAILY_STATS)
            self._notification_services.append(EventService.DAILY)
        if wallet_events:
            self._notification_services.append(EventService.WALLET)
        if decreasing_plot_events:
            self._notification_types.append(EventType.PLOTDECREASE)
        if increasing_plot_events:
            self._notification_types.append(EventType.PLOTINCREASE)

    def get_title_for_event(self, event):
        icon = ""
        if event.priority == EventPriority.HIGH:
            icon = "🚨"
        elif event.priority == EventPriority.NORMAL:
            icon = "⚠️"
        elif event.priority == EventPriority.LOW:
            icon = "ℹ️"

        return f"{icon} {self._title_prefix} {event.service.name}"

    def should_ignore_event(self, event):
        # Automatically ignore Chiadog's spurious "Your harvester appears to be offline!" alerts immediately after a relaunch of container
        # Obviously if the Machinaris container (and thus all farming/harvesting) was just started, there will be a gap in the log... 
        if (self._program_launch_time + MINIMUM_LAUNCH_SECONDS_BEFORE_ALERTING_ABOUT_BEING_OFFLINE) >= time.time():
            if (event.service.name == 'HARVESTER' and event.message.startswith("Your harvester appears to be offline!")) or \
                event.message.startswith("Experiencing networking issues?") or \
                event.message.startswith("Cha-ching!"):
                return True
        # Next only ignore if user has set an "ignore" clause in config.xml for a particular Notifier
        if not "ignore" in self._config:
            return False 
        ignore = self._config["ignore"]
        try:
            # First check for one of type, priority, service, and message as a simple filter
            if 'type' in ignore and ignore['type'] == event.type.name:
                return True
            if 'priority' in ignore and ignore['priority'] == event.priority.name:
                return True
            if 'service' in ignore and ignore['service'] == event.service.name:
                return True
            if 'message' in ignore and re.search(ignore['message'], event.message, re.M|re.I):
                return True
            # Then look for compound ignore clause to invoke json logic
            if 'compound' in ignore:
                rule = json.loads(ignore['compound'])
                data = {   
                    "type" : event.type.name.lower(), 
                    "priority" : event.priority.name.lower(),
                    "service" : event.service.name.lower(), 
                    "message" : event.message
                }
                logging.debug("Rule: {0}".format(json.loads(ignore['compound'])))
                logging.debug("Data: {0}".format(data))
                result = jsonLogic(rule, data)                        
                logging.debug("Result: {0}".format(result))
                return result
        except Exception as ex:
            logging.error("Ignore config '{0}' error {1}".format(ignore, str(ex)))
            traceback.print_exc()
        return False

    def should_allow_event(self, event):
        # Next only allow if user has set an "allow" clause in config.xml for a particular Notifier
        if not "allow" in self._config:
            return True  # By default allow all notifications if no "allow" filter is set
        allow = self._config["allow"]
        try:
            # First check for one of type, priority, service, and message as a simple filter
            if 'type' in allow and allow['type'] == event.type.name:
                return True
            if 'priority' in allow and allow['priority'] == event.priority.name:
                return True
            if 'service' in allow and allow['service'] == event.service.name:
                return True
            if 'message' in allow and re.search(allow['message'], event.message, re.M|re.I):
                return True
            # Then look for compound allow clause to invoke json logic
            if 'compound' in allow:
                rule = json.loads(allow['compound'])
                data = {   
                    "type" : event.type.name.lower(), 
                    "priority" : event.priority.name.lower(),
                    "service" : event.service.name.lower(), 
                    "message" : event.message
                }
                logging.debug("Rule: {0}".format(json.loads(allow['compound'])))
                logging.debug("Data: {0}".format(data))
                result = jsonLogic(rule, data)                        
                logging.debug("Result: {0}".format(result))
                return result
        except Exception as ex:
            logging.error("Allow config '{0}' error {1}".format(allow, str(ex)))
            traceback.print_exc()
        return False

    @abstractmethod
    def send_events_to_user(self, events: List[Event]) -> bool:
        """Implementation specific to the integration"""
        pass
