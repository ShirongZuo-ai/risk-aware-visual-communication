from __future__ import annotations

import unittest

from scripts.audit_m5e_d_closeout import BUDGETS, METHODS, SCENES


class M5EDCloseoutAuditConstantsTests(unittest.TestCase):
    def test_frozen_matrix_constants(self) -> None:
        self.assertEqual(METHODS, ("uniform", "center_roi", "object_roi", "risk_roi"))
        self.assertEqual(BUDGETS, {"severe": 31466, "low": 32374, "medium": 33509, "high": 34871})
        self.assertEqual(SCENES, tuple(f"S{index}" for index in range(1, 9)))
