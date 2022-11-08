# std
import re
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

# lib
from dateutil import parser as dateutil_parser


@dataclass
class WalletAddedCoinMessage:
    timestamp: datetime
    amount_mojos: int


class WalletAddedCoinParser:
    """This class can parse info log messages from the chia wallet

    You need to have enabled "log_level: INFO" in your chia config.yaml
    The chia config.yaml is usually under ~/.chia/mainnet/config/config.yaml
    """

    def __init__(self, config: Optional[dict] = None):
        logging.info("Enabled parser for wallet activity - added coins.")
        self._prefix = config['prefix']
        self._regex = re.compile(
            r"([0-9:.T-]*) wallet (?:src|" + self._prefix + ").wallet.wallet_(?:state_manager|node).*"
            r"INFO\s*(?:Adding|Adding record to state manager|request) coin:.*'?amount'?: ([0-9]*)"
        )

    def parse(self, logs: str) -> List[WalletAddedCoinMessage]:
        """Parses all harvester activity messages from a bunch of logs

        :param logs: String of logs - can be multi-line
        :returns: A list of parsed messages - can be empty
        """

        parsed_messages = []
        matches = self._regex.findall(logs)
        for match in matches:
            # If Chives (etc), we must multiply by 10,000 due to their fork choices
            mojos = int(match[1])
            if self._prefix == 'chives':
                mojos = mojos * 10000
            elif self._prefix == 'cryptodoge':
                mojos = mojos * 1000000
            elif self._prefix == 'shibgreen' or self._prefix == 'littlelambocoin':
                mojos = mojos * 1000000000
            elif self._prefix == 'stai':
                mojos = mojos * 1000
            logging.info("{0} received {1} at {2}".format(self._prefix, mojos, match[0]))
            parsed_messages.append(
                WalletAddedCoinMessage(
                    timestamp=dateutil_parser.parse(match[0]),
                    amount_mojos=mojos,
                )
            )

        return parsed_messages
