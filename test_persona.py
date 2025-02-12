import unittest
from persona import SisyphePersona

class TestPersonaFormatting(unittest.TestCase):
    def setUp(self):
        self.persona = SisyphePersona(test_mode=True)

    def test_normal_response(self):
        """Test qu'une réponse normale n'est pas mise entre astérisques"""
        response = type('Response', (), {'text': 'La philosophie est une quête de sagesse.'})
        result = self.persona._format_response(response)
        self.assertEqual(result, 'La philosophie est une quête de sagesse.')

    def test_physical_action(self):
        """Test qu'une action physique simple est mise entre astérisques"""
        response = type('Response', (), {'text': 'tourne une page'})
        result = self.persona._format_response(response)
        self.assertEqual(result, '*tourne une page*')

    def test_short_response(self):
        """Test que les réponses simples restent concises"""
        response = type('Response', (), {'text': 'En effet.'})
        result = self.persona._format_response(response)
        self.assertEqual(result, 'En effet.')

    def test_mixed_response(self):
        """Test qu'une réponse avec action et texte est correctement formatée"""
        response = type('Response', (), {'text': '*pose son livre* Exact.'})
        result = self.persona._format_response(response)
        self.assertEqual(result, '*pose son livre* Exact.')

    def test_detailed_explanation(self):
        """Test que les explications plus longues sont conservées"""
        explanation = """Le déterminisme implique que tout effet a une cause.
La liberté n'est qu'une illusion née de notre ignorance des causes."""
        response = type('Response', (), {'text': explanation})
        result = self.persona._format_response(response)
        self.assertEqual(result, explanation)

    def test_greeting_response(self):
        """Test que les salutations sont minimalistes"""
        response = type('Response', (), {'text': '*lève brièvement les yeux*'})
        result = self.persona._format_response(response)
        self.assertEqual(result, '*lève brièvement les yeux*')


    def test_user_action_detection(self):
        """Test la détection des actions utilisateur"""
        self.assertTrue(self.persona._detect_user_action("*te lance une pomme*"))
        self.assertFalse(self.persona._detect_user_action("Bonjour"))
        self.assertFalse(self.persona._detect_user_action("*début* milieu *fin"))


if __name__ == '__main__':
    unittest.main()