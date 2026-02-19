import csv
import os
from itertools import permutations
from threading import Lock
from typing import Dict, List, Optional

from loguru import logger

from src.core.domain.detection import Detection
from src.core.domain.street import Street


class PreflopStrategyService:
    """
    Provides preflop lookup for a concrete BTN open spot:
    all players before BTN folded and hero is on BTN.
    """

    ENV_PATH_KEY = "BTN_OPEN_STRATEGY_CSV"
    DEFAULT_PATH = "/Users/ross/Downloads/PLO50_100_6_F-F-F-R100-F_BB_RAISE100.csv"

    _cache_lock = Lock()
    _combo_cache: Dict[str, Dict[str, Dict[str, float]]] = {}

    @classmethod
    def get_btn_open_advice(
            cls,
            player_cards: List[Detection],
            positions: Dict[int, Detection],
            street: Optional[Street],
            strategy_path: Optional[str] = None
    ) -> Optional[Dict]:
        if street != Street.PREFLOP:
            return None

        hero_position = cls._extract_hero_position(positions)
        if hero_position != "BTN":
            return None

        if not cls._is_folded_to_btn(positions):
            return None

        path = strategy_path or os.getenv(cls.ENV_PATH_KEY, cls.DEFAULT_PATH)
        combo_map = cls._load_combo_map(path)
        if not combo_map:
            return None

        combo = cls._find_combo(player_cards, combo_map)
        if not combo:
            return None

        row = combo_map[combo]
        weight = row["weight"]
        ev = row["ev"]

        return {
            "scenario": "BTN open (folded to hero)",
            "action": "RAISE 100",
            "combo": combo,
            "weight": round(weight, 4),
            "ev": round(ev, 3),
            "source": os.path.basename(path),
            "summary": f"R100 {weight * 100:.1f}% | EV {ev:.2f}"
        }

    @classmethod
    def _load_combo_map(cls, path: str) -> Optional[Dict[str, Dict[str, float]]]:
        if not path:
            return None

        with cls._cache_lock:
            if path in cls._combo_cache:
                return cls._combo_cache[path]

        if not os.path.exists(path):
            logger.warning(f"BTN strategy CSV not found: {path}")
            with cls._cache_lock:
                cls._combo_cache[path] = {}
            return None

        combo_map: Dict[str, Dict[str, float]] = {}

        try:
            with open(path, newline="", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    combo = (row.get("combo") or "").strip()
                    if not combo:
                        continue

                    try:
                        weight = float(row.get("weight", 0))
                        ev = float(row.get("ev", 0))
                    except (TypeError, ValueError):
                        continue

                    combo_map[combo] = {"weight": weight, "ev": ev}
        except Exception as exc:
            logger.error(f"Failed to load BTN strategy CSV: {exc}")
            with cls._cache_lock:
                cls._combo_cache[path] = {}
            return None

        with cls._cache_lock:
            cls._combo_cache[path] = combo_map

        logger.info(f"Loaded BTN strategy rows: {len(combo_map)} from {path}")
        return combo_map

    @staticmethod
    def _extract_hero_position(positions: Dict[int, Detection]) -> Optional[str]:
        hero_detection = positions.get(1)
        if hero_detection is None or not hero_detection.position_name:
            return None
        return PreflopStrategyService._normalize_position_name(hero_detection.position_name)

    @staticmethod
    def _normalize_position_name(name: str) -> str:
        value = name.strip().upper()
        for suffix in ("_FOLD", "_LOW"):
            if value.endswith(suffix):
                value = value[:-len(suffix)]
        return value

    @staticmethod
    def _is_folded_to_btn(positions: Dict[int, Detection]) -> bool:
        labels = {d.position_name.upper() for d in positions.values() if d and d.position_name}
        required = {"EP_FOLD", "MP_FOLD", "CO_FOLD"}
        return required.issubset(labels)

    @classmethod
    def _find_combo(cls, player_cards: List[Detection], combo_map: Dict[str, Dict[str, float]]) -> Optional[str]:
        if not player_cards:
            return None

        # Keep 4 best-scoring cards to be resilient to occasional extra matches.
        ordered = sorted(player_cards, key=lambda d: d.match_score, reverse=True)[:4]
        if len(ordered) != 4:
            return None

        csv_cards = []
        for card in ordered:
            converted = cls._to_csv_card(card.template_name)
            if not converted:
                return None
            csv_cards.append(converted)

        # CSV may store combinations in different card order.
        for perm in set(permutations(csv_cards, 4)):
            combo = "".join(perm)
            if combo in combo_map:
                return combo

        return None

    @staticmethod
    def _to_csv_card(template_name: str) -> Optional[str]:
        if not template_name or len(template_name) < 2:
            return None

        rank = template_name[:-1].upper()
        suit = template_name[-1].lower()

        if rank == "10":
            rank = "T"

        valid_ranks = {"A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"}
        valid_suits = {"s", "h", "d", "c"}

        if rank not in valid_ranks or suit not in valid_suits:
            return None

        return f"{rank}{suit}"
