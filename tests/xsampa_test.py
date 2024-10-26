import unittest

from citylex import xsampa


class XSAMPATest(unittest.TestCase):
    def test_a(self):
        self.assertEqual(xsampa.ipa_to_xsampa("ɑː"), "A:")

    def test_ch(self):
        self.assertEqual(xsampa.ipa_to_xsampa("t͡ʃ"), "tS")

    def test_syllabic_m(self):
        self.assertEqual(xsampa.ipa_to_xsampa("m̩"), "m_=")

    def test_schwa(self):
        self.assertEqual(xsampa.ipa_to_xsampa("ɘ"), "@\\")

    def test_y(self):
        self.assertEqual(xsampa.ipa_to_xsampa("ʏ"), "Y")

    def test_spaces(self):
        self.assertEqual(xsampa.ipa_to_xsampa("t͡ʃ ɾ"), "tS 4")


if __name__ == "__main__":
    unittest.main()
