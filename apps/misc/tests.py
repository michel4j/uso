import unittest
from misc.utils import MultiKeyDict


class TestMultiKeyDict(unittest.TestCase):
    def setUp(self):
        # Initial dictionary with tuple keys
        self.source = {
            ('a', 'b'): 1,
            ('c', 'd', 'e'): 2,
            ('f',): 3
        }
        self.mkd = MultiKeyDict(self.source.copy())

    def test_getitem_with_single_key(self):
        self.assertEqual(self.mkd['a'], 1)
        self.assertEqual(self.mkd['b'], 1)
        self.assertEqual(self.mkd['c'], 2)
        self.assertEqual(self.mkd['e'], 2)
        self.assertEqual(self.mkd['f'], 3)

    def test_getitem_with_tuple_key(self):
        self.assertEqual(self.mkd[('a', 'b')], 1)
        self.assertEqual(self.mkd[('c', 'e')], 2)
        with self.assertRaises(KeyError):
            _ = self.mkd[('x', 'y')]

    def test_setitem_with_new_tuple(self):
        self.mkd[('x', 'y')] = 4
        self.assertEqual(self.mkd['x'], 4)
        self.assertEqual(self.mkd['y'], 4)

    def test_setitem_with_existing_key(self):
        self.mkd['a'] = 10
        self.assertEqual(self.mkd['a'], 10)
        self.assertEqual(self.mkd['b'], 10)

    def test_delitem(self):
        del self.mkd['a']
        with self.assertRaises(KeyError):
            _ = self.mkd['a']
        # 'b' should also be removed
        with self.assertRaises(KeyError):
            _ = self.mkd['b']

    def test_contains(self):
        self.assertIn('a', self.mkd)
        self.assertIn('d', self.mkd)
        self.assertNotIn('z', self.mkd)
        self.assertTrue(self.mkd.__contains__(('a', 'z')))

    def test_len(self):
        self.assertEqual(len(self.mkd), 3)
        self.mkd[('x', 'y')] = 4
        self.assertEqual(len(self.mkd), 4)

    def test_get(self):
        self.assertEqual(self.mkd.get('a'), 1)
        self.assertEqual(self.mkd.get('z', 'default'), 'default')

if __name__ == '__main__':
    unittest.main()# Create your tests here.
