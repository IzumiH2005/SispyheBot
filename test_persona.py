import unittest
from persona import SisyphePersona

class TestPersonaFormatting(unittest.TestCase):
    def setUp(self):
        self.persona = SisyphePersona()

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

    def test_explanation_response(self):
        """Test qu'une explication est précédée d'une action"""
        response = type('Response', (), {'text': 'Je vais t\'expliquer le concept du temps cyclique.'})
        result = self.persona._format_response(response)
        self.assertTrue(result.startswith('*pose son livre*'))
        self.assertTrue('expliquer le concept du temps cyclique' in result)

    def test_already_formatted(self):
        """Test qu'un texte déjà formaté avec des astérisques n'est pas modifié"""
        response = type('Response', (), {'text': '*ferme son livre*'})
        result = self.persona._format_response(response)
        self.assertEqual(result, '*ferme son livre*')

if __name__ == '__main__':
    unittest.main()
