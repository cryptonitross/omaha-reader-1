import os
import tempfile
import unittest

from src.core.domain.detection import Detection
from src.core.domain.street import Street
from src.core.service.preflop_strategy_service import PreflopStrategyService


def _detection(name: str, score: float = 1.0) -> Detection:
    return Detection(name=name, center=(0, 0), bounding_rect=(0, 0, 10, 10), match_score=score)


class PreflopStrategyServiceTest(unittest.TestCase):
    def test_btn_open_advice_found(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, newline="", suffix=".csv") as f:
            f.write("combo,weight,ev\n")
            f.write("AsTsAhAd,0.75,1.23\n")
            csv_path = f.name

        try:
            cards = [_detection("AS"), _detection("TS"), _detection("AH"), _detection("AD")]
            positions = {
                1: _detection("BTN"),
                2: _detection("SB"),
                3: _detection("EP_fold"),
                4: _detection("MP_fold"),
                5: _detection("CO_fold"),
                6: _detection("BB"),
            }

            advice = PreflopStrategyService.get_btn_open_advice(
                player_cards=cards,
                positions=positions,
                street=Street.PREFLOP,
                strategy_path=csv_path
            )

            self.assertIsNotNone(advice)
            self.assertEqual("AsTsAhAd", advice["combo"])
            self.assertEqual("RAISE 100", advice["action"])
        finally:
            os.remove(csv_path)

    def test_btn_open_advice_requires_btn(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, newline="", suffix=".csv") as f:
            f.write("combo,weight,ev\n")
            f.write("AsTsAhAd,0.75,1.23\n")
            csv_path = f.name

        try:
            cards = [_detection("AS"), _detection("TS"), _detection("AH"), _detection("AD")]
            positions = {
                1: _detection("CO"),
                2: _detection("SB"),
                3: _detection("EP_fold"),
                4: _detection("MP_fold"),
                5: _detection("BTN"),
                6: _detection("BB"),
            }

            advice = PreflopStrategyService.get_btn_open_advice(
                player_cards=cards,
                positions=positions,
                street=Street.PREFLOP,
                strategy_path=csv_path
            )

            self.assertIsNone(advice)
        finally:
            os.remove(csv_path)

