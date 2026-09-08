import inspect
import unittest

from app.providers.base import LLMProvider
from app.providers.fake_provider import FakeProvider
from app.providers.gemini_provider import GeminiProvider


class ContratoLLMProviderTests(unittest.IsolatedAsyncioTestCase):

    def test_llmprovider_no_se_puede_instanciar(self):
        with self.assertRaises(TypeError):
            LLMProvider()

    def test_firma_base_incluye_system_instruction_y_tools(self):
        params = list(inspect.signature(LLMProvider.generate).parameters)
        self.assertEqual(params, ["self", "messages", "system_instruction", "tools"])

    def test_fake_provider_cumple_el_contrato(self):
        provider = FakeProvider()
        self.assertIsInstance(provider, LLMProvider)

        params = list(inspect.signature(FakeProvider.generate).parameters)
        self.assertEqual(params, ["self", "messages", "system_instruction", "tools"])

    async def test_fake_provider_acepta_system_instruction_como_el_agent(self):
        provider = FakeProvider()

        response = await provider.generate(
            [{"role": "user", "content": "Hola"}],
            system_instruction="instruccion",
        )

        self.assertIn("content", response)
        self.assertIsInstance(response["content"], str)

    async def test_fake_provider_acepta_tools(self):
        provider = FakeProvider()

        response = await provider.generate(
            [{"role": "user", "content": "Hola"}],
            system_instruction="instruccion",
            tools=[{"name": "dummy"}],
        )

        self.assertIn("content", response)

    def test_gemini_provider_cumple_el_contrato(self):
        self.assertTrue(issubclass(GeminiProvider, LLMProvider))

        base_params = list(inspect.signature(LLMProvider.generate).parameters)
        impl_params = list(inspect.signature(GeminiProvider.generate).parameters)

        self.assertEqual(base_params, impl_params)


if __name__ == "__main__":
    unittest.main()
