from cabot.metricsapp.utils import interval_str_to_int
from django.test import TestCase


class TestElasticsearchSource(TestCase):
    def test_interval_str_to_int(self):
        # Valid inputs
        self.assertEqual(interval_str_to_int('10s'), 10)
        self.assertEqual(interval_str_to_int('15m'), 15 * 60)
        self.assertEqual(interval_str_to_int('12h'), 12 * 60 * 60)
        self.assertEqual(interval_str_to_int('2d'), 2 * 60 * 60 * 24)
        # Invalid inputs
        with self.assertRaises(ValueError):
            interval_str_to_int('')
        with self.assertRaises(ValueError):
            interval_str_to_int('5x')
        with self.assertRaises(ValueError):
            interval_str_to_int('one hour')
