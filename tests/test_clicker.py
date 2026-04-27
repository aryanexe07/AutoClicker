import unittest
from unittest.mock import MagicMock, patch

from autoclicker.core.clicker import ClickerThread


class TestClickerButtonMapping(unittest.TestCase):
    """Test that middle click is properly passed to pyautogui for all click types."""

    def _make_config(self, button: str, click_behaviour: str) -> dict:
        """Helper to create a minimal config dict."""
        return {
            "button": button,
            "click_behaviour": click_behaviour,
            "type": click_behaviour,
            "interval_ms": 100,
            "location_mode": "Follow cursor",
            "x": 0,
            "y": 0,
            "repeat_mode": "Infinite",
            "repeat_count": 1,
            "timer_mode": "None",
            "timer_seconds": 1,
            "start_delay": 0,
            "hotkey_start": "F6",
            "hotkey_stop": "F7",
        }

    def test_middle_button_single_click(self):
        """Middle + Single click should pass button='middle' with 1 click."""
        config = self._make_config("Middle", "single")
        mock_pos = MagicMock()
        mock_pos.x = 100
        mock_pos.y = 200
        with patch("autoclicker.core.clicker.pyautogui.click") as mock_click:
            with patch("autoclicker.core.clicker.pyautogui.position", return_value=mock_pos):
                thread = ClickerThread(config)
                thread._do_click()
                mock_click.assert_called_once_with(
                    x=100, y=200, clicks=1, interval=0, button="middle"
                )

    def test_middle_button_double_click(self):
        """Middle + Double click should pass button='middle' with 2 clicks and small interval."""
        config = self._make_config("Middle", "double")
        mock_pos = MagicMock()
        mock_pos.x = 100
        mock_pos.y = 200
        with patch("autoclicker.core.clicker.pyautogui.click") as mock_click:
            with patch("autoclicker.core.clicker.pyautogui.position", return_value=mock_pos):
                thread = ClickerThread(config)
                thread._do_click()
                mock_click.assert_called_once_with(
                    x=100, y=200, clicks=2, interval=0, button="middle"
                )

    def test_middle_button_triple_click(self):
        """Middle + Triple click should pass button='middle' with 3 clicks and small interval."""
        config = self._make_config("Middle", "triple")
        mock_pos = MagicMock()
        mock_pos.x = 100
        mock_pos.y = 200
        with patch("autoclicker.core.clicker.pyautogui.click") as mock_click:
            with patch("autoclicker.core.clicker.pyautogui.position", return_value=mock_pos):
                thread = ClickerThread(config)
                thread._do_click()
                mock_click.assert_called_once_with(
                    x=100, y=200, clicks=3, interval=0.03, button="middle"
                )

    def test_left_button_single_click(self):
        """Left + Single click should pass button='left' (sanity check)."""
        config = self._make_config("Left", "single")
        mock_pos = MagicMock()
        mock_pos.x = 100
        mock_pos.y = 200
        with patch("autoclicker.core.clicker.pyautogui.click") as mock_click:
            with patch("autoclicker.core.clicker.pyautogui.position", return_value=mock_pos):
                thread = ClickerThread(config)
                thread._do_click()
                mock_click.assert_called_once_with(
                    x=100, y=200, clicks=1, interval=0, button="left"
                )

    def test_right_button_single_click(self):
        """Right + Single click should pass button='right' (sanity check)."""
        config = self._make_config("Right", "single")
        mock_pos = MagicMock()
        mock_pos.x = 100
        mock_pos.y = 200
        with patch("autoclicker.core.clicker.pyautogui.click") as mock_click:
            with patch("autoclicker.core.clicker.pyautogui.position", return_value=mock_pos):
                thread = ClickerThread(config)
                thread._do_click()
                mock_click.assert_called_once_with(
                    x=100, y=200, clicks=1, interval=0, button="right"
                )

    def test_middle_button_fixed_xy_location(self):
        """Middle click with Fixed XY location should pass x, y coordinates."""
        config = self._make_config("Middle", "single")
        config["location_mode"] = "Fixed XY"
        config["x"] = 100
        config["y"] = 200
        with patch("autoclicker.core.clicker.pyautogui.click") as mock_click:
            thread = ClickerThread(config)
            thread._do_click()
            mock_click.assert_called_once_with(
                x=100, y=200, clicks=1, interval=0, button="middle"
            )


class TestClickerMultiPoint(unittest.TestCase):
    def _make_multi_config(self) -> dict:
        return {
            "button": "Left",
            "click_behaviour": "single",
            "type": "single",
            "interval_h": 0,
            "interval_m": 0,
            "interval_s": 0,
            "interval_ms": 10,
            "location_mode": "Fixed XY",
            "x": 0,
            "y": 0,
            "repeat_mode": "Fixed count",
            "repeat_count": 2,
            "timer_mode": "None",
            "timer_seconds": 10,
            "start_delay": 0,
            "hotkey_start": "F6",
            "hotkey_stop": "F7",
            "multi_mode": True,
        }

    def test_multipoint_fixed_count_stops_after_passes(self):
        config = self._make_multi_config()
        sequence = [{"x": 10, "y": 20, "delay_ms": 0}, {"x": 30, "y": 40, "delay_ms": 0}]
        with patch("autoclicker.core.clicker.pyautogui.click") as mock_click:
            with patch("autoclicker.core.clicker.time.sleep"):
                thread = ClickerThread(config, multi_sequence=sequence)
                thread.run()
                self.assertEqual(mock_click.call_count, 4)

    def test_multipoint_session_count_tracks_completed_passes(self):
        config = self._make_multi_config()
        sequence = [{"x": 1, "y": 2, "delay_ms": 0}, {"x": 3, "y": 4, "delay_ms": 0}]
        with patch("autoclicker.core.clicker.pyautogui.click"):
            with patch("autoclicker.core.clicker.time.sleep"):
                thread = ClickerThread(config, multi_sequence=sequence)
                thread.run()
                self.assertEqual(thread._session_clicks, 2)


if __name__ == "__main__":
    unittest.main()
