from guild import shape, plist
import unittest


class Persistent(unittest.TestCase):

    def test_plist_match_plist(self):
        self.assertTrue(shape.is_shaped(plist([1, 2, 3]), plist))

    def test_plist_match_typed_plist(self):
        self.assertTrue(shape.is_shaped(plist([1, 2, 3]), plist[int]))
        self.assertFalse(shape.is_shaped(plist([1, '2', 3]), plist[int]))
