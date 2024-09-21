import unittest

from citylex import xsampa


class XSAMPATest(unittest.TestCase):
    def test_1(self):
        self.assertEqual(xsampa.ipa_to_xsampa("ɑː"), "A:")

    def test_2(self):
        self.assertEqual(xsampa.ipa_to_xsampa("t͡ʃ"), "tS")

    def test_3(self):
        self.assertEqual(xsampa.ipa_to_xsampa("m̩"), "m_=")

    def test_4(self):
        self.assertEqual(xsampa.ipa_to_xsampa("ɘ"), "@\\")

    def test_5(self):
        self.assertEqual(xsampa.ipa_to_xsampa("ʏ"), "Y")

    def test_spaces(self):
        self.assertEqual(xsampa.ipa_to_xsampa("t͡ʃ ɾ"), "tS 4")


if __name__ == "__main__":
    unittest.main()
