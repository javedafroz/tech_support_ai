"""Structured logging for live integration tests."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOGGER_NAME = "live_integration"


def configure_live_integration_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    logger.addHandler(console)

    log_dir = Path(__file__).resolve().parent / "artifacts"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "live_integration.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def log_scenario_start(scenario_id: str, run_reference: str, mode: str) -> None:
    logger = get_logger()
    logger.info("=" * 72)
    logger.info("SCENARIO START  id=%s  ref=%s  mode=%s", scenario_id, run_reference, mode)
    logger.info("=" * 72)


def log_scenario_end(
    scenario_id: str,
    *,
    success: bool,
    ticket_number: str | None,
    turns: int,
    reason: str | None = None,
) -> None:
    logger = get_logger()
    status = "PASS" if success else "FAIL"
    logger.info("-" * 72)
    logger.info(
        "SCENARIO %s  id=%s  turns=%d  ticket=%s",
        status,
        scenario_id,
        turns,
        ticket_number or "—",
    )
    if reason:
        logger.info("Reason: %s", reason)
    logger.info("-" * 72)


def log_turn(
    *,
    scenario_id: str,
    turn_index: int,
    user_message: str,
    assistant_content: str,
    detected_intent: str | None,
    system_statuses: list[str],
    assistant_card: dict | None,
) -> None:
    logger = get_logger()
    logger.info("")
    logger.info("[Turn %d] %s", turn_index, scenario_id)
    logger.info("  USER     │ %s", user_message.replace("\n", " "))
    if system_statuses:
        logger.info("  STATUS   │ %s", " → ".join(system_statuses))
    if detected_intent:
        logger.info("  INTENT   │ %s", detected_intent)
    if assistant_content:
        logger.info("  SUPPORT  │ %s", assistant_content.replace("\n", " "))
    if assistant_card:
        logger.info("  CARD     │ %s", assistant_card)


def log_user_sim_note(notes: str | None) -> None:
    if notes:
        get_logger().debug("  USER SIM │ %s", notes)
