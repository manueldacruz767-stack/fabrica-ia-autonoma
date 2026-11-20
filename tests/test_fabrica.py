import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import executar_agente
import fabrica_core
import orquestrador


class ErroTemporario(Exception):
    code = 503


class ModelosFalsos:
    def __init__(self):
        self.modelos = []

    def generate_content(self, model, contents, config=None):
        self.modelos.append(model)
        if model == "gemini-3.1-flash-lite":
            raise ErroTemporario("UNAVAILABLE")
        return SimpleNamespace(text="resposta de teste")


class TestesFabricaCore(unittest.TestCase):
    def test_carregar_skill_devolve_conteudo(self):
        conteudo = fabrica_core.carregar_skill("arquiteto")
        self.assertIn("Arquiteto", conteudo)

    def test_carregar_skill_recusa_caminho_invalido(self):
        conteudo = fabrica_core.carregar_skill("../../etc/passwd")
        self.assertNotIn("root:", conteudo)
        self.assertIn("especialista", conteudo)

    def test_prompt_contem_skill_e_tarefa(self):
        prompt = fabrica_core.construir_prompt("qa", "Validar build", "contexto")
        self.assertIn("SKILL_OFICIAL", prompt)
        self.assertIn("Validar build", prompt)
        self.assertIn("contexto", prompt)

    def test_comando_com_operadores_e_recusado(self):
        with self.assertRaises(ValueError):
            fabrica_core.validar_comando("git status && rm -rf /")

    def test_python_arbitrario_e_bloqueado(self):
        with self.assertRaises(ValueError):
            fabrica_core.validar_comando("python3 -c print(1)")

    def test_subcomando_nao_permitido(self):
        with self.assertRaises(ValueError):
            fabrica_core.validar_comando("git push --force")

    def test_deploy_producao_e_bloqueado(self):
        with self.assertRaises(ValueError):
            fabrica_core.validar_comando("vercel deploy --prod")

    def test_comando_bloqueado_sem_optin(self):
        with patch.dict(os.environ, {"FABRICA_ACOES_EXTERNAS": "false"}):
            resultado = fabrica_core.executar_comando("git status --short")
        self.assertIn("BLOQUEADO", resultado)

    def test_comando_permitido_com_optin(self):
        with patch.dict(os.environ, {"FABRICA_ACOES_EXTERNAS": "1"}):
            resultado = fabrica_core.executar_comando("git status --short", cwd=str(RAIZ))
        self.assertTrue(resultado.startswith("[OK]") or resultado.startswith("[FALHOU"))

    def test_fallback_de_modelo(self):
        modelos = ModelosFalsos()
        cliente = SimpleNamespace(models=modelos)
        with patch.object(fabrica_core, "chave_api", return_value="chave-teste"), patch.object(
            fabrica_core.genai, "Client", return_value=cliente
        ), patch.object(fabrica_core.time, "sleep"):
            geracao = fabrica_core.gerar_texto("prompt", tentativas=1)
        self.assertEqual(geracao.modelo, "gemini-3.5-flash-lite")
        self.assertEqual(geracao.texto, "resposta de teste")
        self.assertEqual(modelos.modelos, ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"])


class TestesEntradas(unittest.TestCase):
    def test_orquestrador_dry_run_gravaria_relatorio(self):
        with tempfile.TemporaryDirectory() as diretorio:
            destino = Path(diretorio) / "relatorio.md"
            codigo = orquestrador.main(["--ideia", "Projeto Teste", "--dry-run", "--saida", str(destino)])
            self.assertEqual(codigo, 0)
            conteudo = destino.read_text(encoding="utf-8")
            self.assertIn("Projeto Teste", conteudo)
            self.assertIn("scrum_master", conteudo)

    def test_agente_dry_run_sem_api(self):
        resultado = executar_agente.executar_agente_autonomo("devops", "Validar fluxo", dry_run=True)
        self.assertIn("devops", resultado)
        self.assertIn("Validar fluxo", resultado)


if __name__ == "__main__":
    unittest.main()
