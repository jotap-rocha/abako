"""SPEC-015: operação local (`scripts/operacao.py`). Sem Docker real, sem rede e nunca o prd:
todo comando passa por um `Sistema` falso que só registra o que seria executado.

Os valores esperados (idades, revisões, ordem dos comandos) foram escritos à mão.
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
import threading
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from db.alvo import VAR_CONFIRMA_PRD
from scripts import operacao
from scripts.config_local import porta_valida
from scripts.operacao import (
    Falha,
    Operador,
    Recusa,
    Resultado,
    SistemaReal,
    ambiente_filho,
    build_desatualizado,
    descrever_excecao,
    e_processo_do_abako,
    formatar_idade,
    normalizar_drive,
    pendentes_de,
    procurar_executavel,
    revisoes_de,
    saida_segura,
    ultimo_backup,
)

PY = "PY"
AGORA = datetime(2026, 11, 20, 12, 0, 0)
LINHA_API = r"C:\repo\.venv\Scripts\python.exe -m backend"
RE_URL_COM_CREDENCIAL = re.compile(r"://[^\s:/@]+:[^\s@]+@")


class SistemaFalso:
    """Registra comandos e devolve respostas combinadas; nada é executado de verdade."""

    def __init__(self, *, terminal: bool = True, digitado: Sequence[str] = ()) -> None:
        self.comandos: list[tuple[list[str], dict[str, str], bool]] = []
        self.regras: list[tuple[tuple[str, ...], Resultado, str | None]] = []
        self.terminal = terminal
        self.digitado = list(digitado)
        self.perguntas: list[str] = []
        self.vivos: set[int] = set()
        self.linhas: dict[int, str] = {}
        self.encerrados: list[int] = []
        self.iniciados: list[tuple[list[str], dict[str, str], Path]] = []
        self.portas: set[int] = set()
        self.api_ok = True
        self.log_inicial = ""
        self.url_aberta: list[str] = []
        self.explodir_em: tuple[str, ...] | None = None

    def quando(
        self, *tokens: str, saida: str = "", codigo: int = 0, alvo: str | None = None
    ) -> None:
        self.regras.insert(0, (tokens, Resultado(codigo, saida), alvo))  # a mais nova vence

    def rodar(
        self,
        cmd: Sequence[str],
        *,
        cwd: Path | None = None,
        env_extra: Mapping[str, str] | None = None,
        capturar: bool = True,
    ) -> Resultado:
        extra = dict(env_extra or {})
        self.comandos.append((list(cmd), extra, capturar))
        if self.explodir_em and all(t in cmd for t in self.explodir_em):
            raise RuntimeError("falha em postgresql://app:MARC_SENHA_9@127.0.0.1:5433/prd")
        for tokens, resultado, alvo in self.regras:
            if all(t in cmd for t in tokens) and (alvo is None or extra.get("ABAKO_ENV") == alvo):
                return resultado
        return Resultado(0, "")

    def iniciar_em_segundo_plano(
        self, cmd: Sequence[str], *, cwd: Path, env_extra: Mapping[str, str], log: Path
    ) -> int:
        self.iniciados.append((list(cmd), dict(env_extra), log))
        log.write_text(self.log_inicial, encoding="utf-8")
        self.vivos.add(4242)
        self.linhas[4242] = LINHA_API
        return 4242

    def processo_vivo(self, pid: int) -> bool:
        return pid in self.vivos

    def linha_de_comando(self, pid: int) -> str | None:
        return self.linhas.get(pid)

    def encerrar(self, pid: int) -> None:
        self.encerrados.append(pid)
        self.vivos.discard(pid)

    def porta_ocupada(self, porta: int) -> bool:
        return porta in self.portas

    def api_responde(self, porta: int) -> bool:
        return self.api_ok

    def tem_terminal(self) -> bool:
        return self.terminal

    def pedir(self, pergunta: str) -> str:
        self.perguntas.append(pergunta)
        return self.digitado.pop(0) if self.digitado else ""

    def agora(self) -> datetime:
        return AGORA

    def dormir(self, segundos: float) -> None:
        return None

    def abrir_url(self, url: str) -> None:
        self.url_aberta.append(url)

    def rotulos(self) -> list[str]:
        return [" ".join(c[1:]) if c[0] == PY else " ".join(c) for c, _, _ in self.comandos]

    def confirmacoes_do_prd(self) -> list[dict[str, str]]:
        return [e for _, e, _ in self.comandos if e.get(VAR_CONFIRMA_PRD) == "sim"]


class Ambiente:
    def __init__(self, tmp: Path, sis: SistemaFalso) -> None:
        self.raiz = tmp / "repo"
        self.estado = tmp / "estado"
        self.backups = tmp / "backups"
        (self.raiz / "frontend" / "src").mkdir(parents=True)
        self.backups.mkdir()
        self.sis = sis
        sis.quando("docker", "inspect", saida="running|healthy\n")
        sis.quando(
            "scripts.config_local",
            saida=json.dumps({"conteiner": "proj-postgres", "pasta": str(self.backups)}),
        )
        self.op = Operador(sis, self.raiz, self.estado, porta=8080, python=PY)

    def executar(self, *argv: str) -> int:
        return operacao.main(
            list(argv), sistema=self.sis, raiz=self.raiz, pasta_estado=self.estado, python=PY
        )

    def frontend_em_dia(self) -> None:
        """dist mais novo que tudo; node_modules presente."""
        (self.raiz / "frontend" / "node_modules").mkdir(exist_ok=True)
        (self.raiz / "frontend" / "dist").mkdir(exist_ok=True)
        (self.raiz / "frontend" / "package.json").write_text("{}", encoding="utf-8")
        (self.raiz / "frontend" / "openapi.json").write_text("{}", encoding="utf-8")
        (self.raiz / "frontend" / "src" / "App.tsx").write_text("x", encoding="utf-8")
        for nome in ("package.json", "openapi.json", "src/App.tsx"):
            os.utime(self.raiz / "frontend" / nome, (1000, 1000))
        index = self.raiz / "frontend" / "dist" / "index.html"
        index.write_text("<html>", encoding="utf-8")
        os.utime(index, (2000, 2000))

    def backup_prd(self, nome: str) -> None:
        (self.backups / nome).write_bytes(b"x")

    def git_limpo_na_main(self, branch: str = "main") -> None:
        self.sis.quando("git", "status", "--porcelain", saida="")
        self.sis.quando("git", "branch", "--show-current", saida=branch + "\n")

    def estado_api(self, pid: int = 4242, env: str = "prd") -> None:
        self.estado.mkdir(parents=True, exist_ok=True)
        (self.estado / "api.pid").write_text(
            json.dumps({"pid": pid, "env": env, "porta": 8080}), encoding="utf-8"
        )
        self.sis.vivos.add(pid)
        self.sis.linhas[pid] = LINHA_API


@pytest.fixture(autouse=True)
def _sem_porta_do_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Os testes esperam a porta padrão; uma ABAKO_PORTA do terminal do dono não pode mudá-los."""
    monkeypatch.delenv("ABAKO_PORTA", raising=False)


@pytest.fixture
def amb(tmp_path: Path) -> Ambiente:
    return Ambiente(tmp_path, SistemaFalso())


def _prd_de_pe(amb: Ambiente, digitado: Sequence[str]) -> None:
    amb.sis.digitado = list(digitado)


# ------------------------------------------------------------------ funções puras


def test_normalizar_drive_poe_a_letra_em_maiusculo() -> None:
    assert normalizar_drive(r"d:\projetos\abako") == r"D:\projetos\abako"
    assert normalizar_drive(r"D:\projetos\abako") == r"D:\projetos\abako"
    assert normalizar_drive("c:/x/y") == "C:/x/y"
    assert normalizar_drive("/home/x") == "/home/x"
    assert normalizar_drive("") == ""


def _frontend(tmp: Path) -> Path:
    f = tmp / "frontend"
    (f / "src" / "api").mkdir(parents=True)
    (f / "dist").mkdir()
    for arq in ("package.json", "openapi.json", "src/App.tsx", "src/api/cliente.ts"):
        (f / arq).write_text("x", encoding="utf-8")
        os.utime(f / arq, (900, 900))
    (f / "dist" / "index.html").write_text("x", encoding="utf-8")
    os.utime(f / "dist" / "index.html", (1000, 1000))
    return f


def test_build_em_dia_quando_nada_e_mais_novo_que_o_dist(tmp_path: Path) -> None:
    f = _frontend(tmp_path)
    assert build_desatualizado(f) is None
    os.utime(f / "src" / "App.tsx", (1000, 1000))  # igual ao dist: não é mais novo
    assert build_desatualizado(f) is None


def test_build_desatualizado_sem_dist(tmp_path: Path) -> None:
    f = _frontend(tmp_path)
    (f / "dist" / "index.html").unlink()
    assert build_desatualizado(f) == "dist ausente (o front nunca foi construído)"


@pytest.mark.parametrize(
    "arquivo", ["src/App.tsx", "src/api/cliente.ts", "package.json", "openapi.json"]
)
def test_build_desatualizado_quando_arquivo_e_mais_novo(tmp_path: Path, arquivo: str) -> None:
    f = _frontend(tmp_path)
    os.utime(f / arquivo, (1001, 1001))
    assert build_desatualizado(f) == f"{arquivo} é mais novo que o dist"


NOMES = [
    "abako-prd-20261110-080000.dump.age",
    "abako-prd-20261105-080000.dump.age",
    "abako-tst-20261119-080000.dump.age",  # outro ambiente: não conta
    "abako-prd-20261119-080000.dump.age.parcial",  # parcial: não conta
    "abako-prd-20261201-080000.dump.age",  # data no futuro: não conta
    "leiame.txt",
]


def test_idade_do_backup_vem_da_data_no_nome() -> None:
    achado = ultimo_backup(NOMES, "prd", AGORA)
    assert achado is not None
    nome, idade = achado
    assert nome == "abako-prd-20261110-080000.dump.age"
    assert idade == timedelta(days=10, hours=4)  # 10/11 08:00 até 20/11 12:00
    assert formatar_idade(idade) == "10 dias e 4 horas"
    assert ultimo_backup(["abako-prd-20261120-110000.dump.age"], "prd", AGORA) == (
        "abako-prd-20261120-110000.dump.age",
        timedelta(hours=1),
    )
    assert formatar_idade(timedelta(hours=1)) == "0 dias e 1 hora"
    assert ultimo_backup(["leiame.txt"], "prd", AGORA) is None


def test_backup_de_ate_7_dias_passa_e_de_mais_recusa(amb: Ambiente) -> None:
    amb.backup_prd("abako-prd-20261113-120000.dump.age")  # exatamente 7 dias
    amb.op.exigir_backup_recente()
    for f in amb.backups.iterdir():
        f.unlink()
    amb.backup_prd("abako-prd-20261113-115959.dump.age")  # 7 dias e 1 segundo
    with pytest.raises(Recusa, match=r"7 dias e 0 horas.*abako backup --alvo prd"):
        amb.op.exigir_backup_recente()


def test_sem_backup_do_prd_recusa_e_manda_rodar_o_backup(amb: Ambiente) -> None:
    amb.backup_prd("abako-tst-20261120-110000.dump.age")  # só tst
    with pytest.raises(Recusa, match="abako backup --alvo prd"):
        amb.op.exigir_backup_recente()


def test_processo_do_abako_pela_linha_de_comando() -> None:
    assert e_processo_do_abako(LINHA_API)
    assert e_processo_do_abako("/usr/bin/python3 -m backend")
    assert not e_processo_do_abako("notepad.exe")
    assert not e_processo_do_abako(r"python.exe -m pytest")
    assert not e_processo_do_abako("node.exe -m backend")
    assert not e_processo_do_abako(None)


def test_confirmacao_do_prd_nao_e_herdada_do_terminal() -> None:
    base = {"A": "1", VAR_CONFIRMA_PRD: "sim", "abako_confirma_prd": "sim"}
    assert VAR_CONFIRMA_PRD not in ambiente_filho(base)
    assert "abako_confirma_prd" not in ambiente_filho(base)
    assert ambiente_filho(base)["A"] == "1"
    assert ambiente_filho({}, {VAR_CONFIRMA_PRD: "sim"})[VAR_CONFIRMA_PRD] == "sim"


def test_leitura_das_saidas_do_alembic() -> None:
    assert revisoes_de("0014 (head)\n") == ["0014"]
    assert revisoes_de("0013\n") == ["0013"]
    assert revisoes_de("") == []
    assert revisoes_de("0014 (head)\n0015 (head)\n") == ["0014", "0015"]
    assert revisoes_de("postgresql://u:MARC_SENHA_1@h/d\nINFO [alembic] x") == []
    historico = "0013 -> 0014 (head), leituras do pipeline\n0012 -> 0013, vale com bolsos\n"
    assert pendentes_de(historico) == [
        ("0013", "vale com bolsos"),
        ("0014", "leituras do pipeline"),
    ]


def test_saida_segura_remove_url_senha_e_linhas_perigosas() -> None:
    texto = "\n".join(
        [
            "erro ao conectar postgresql://app:MARC_SENHA_1@127.0.0.1:5433/prd",
            "PASSWORD=MARC_SENHA_2 e senha: MARC_SENHA_3",
            'CONTEXT: COPY t, line 3: "MARC_VALOR"',
            "linha normal",
        ]
    )
    saida = saida_segura(texto)
    assert "MARC_" not in saida
    assert "linha normal" in saida
    assert "<url oculta>" in saida


def test_excecao_so_com_classe_e_sqlstate() -> None:
    class ErroPg(Exception):
        sqlstate = "28P01"

    assert descrever_excecao(ErroPg("postgresql://u:MARC_SENHA_1@h/d")) == (
        "ErroPg (SQLSTATE 28P01)"
    )
    assert descrever_excecao(ValueError("MARC_SENHA_1")) == "ValueError"


# ------------------------------------------------------------------ subir (AC-1)


def test_subir_tst_sobe_banco_inicia_api_so_local_e_mostra_ambiente(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.frontend_em_dia()
    assert amb.executar("subir", "--tst") == 0
    rotulos = amb.sis.rotulos()
    assert rotulos.index("-m scripts.config_local") < rotulos.index("docker compose up -d")
    assert "docker compose up -d" in rotulos
    assert any(r.startswith("docker inspect") and "proj-postgres" in r for r in rotulos)
    assert not any("npm" in r for r in rotulos)  # build em dia: não refaz
    ((cmd, env, log),) = amb.sis.iniciados
    assert cmd == [PY, "-m", "backend"]
    assert env == {"ABAKO_ENV": "tst"}
    assert "0.0.0.0" not in " ".join(cmd)
    assert log == amb.estado / "api.log"
    assert json.loads((amb.estado / "api.pid").read_text(encoding="utf-8")) == {
        "pid": 4242,
        "env": "tst",
        "porta": 8080,
    }
    saida = capsys.readouterr().out
    assert "http://127.0.0.1:8080" in saida
    assert "AMBIENTE: TST (banco de teste)" in saida


def test_subir_usa_prd_por_padrao_com_aviso_e_sem_confirmacao_do_prd(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.frontend_em_dia()
    assert amb.executar("subir") == 0
    ((_, env, _),) = amb.sis.iniciados
    assert env == {"ABAKO_ENV": "prd"}
    assert amb.sis.confirmacoes_do_prd() == []
    assert "AMBIENTE: PRD (dados reais)" in capsys.readouterr().out


def test_subir_refaz_o_build_desatualizado_antes_de_iniciar_a_api(amb: Ambiente) -> None:
    # sem dist e sem node_modules: npm ci, depois npm run build, depois a API
    assert amb.executar("subir", "--tst") == 0
    rotulos = amb.sis.rotulos()
    assert rotulos.index("npm ci") < rotulos.index("npm run build")
    assert rotulos.index("docker compose up -d") < rotulos.index("npm run build")
    assert len(amb.sis.iniciados) == 1
    ci = next(c for c in amb.sis.comandos if c[0] == ["npm", "ci"])
    assert ci[2] is False  # a saída do npm vai direto ao terminal


def test_subir_recusa_porta_ocupada_por_outro_programa(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.sis.portas.add(8080)
    assert amb.executar("subir") == 2
    assert amb.sis.rotulos() == ["-m scripts.config_local"]  # só a configuração; nem o banco
    assert amb.sis.iniciados == []
    assert "porta 8080" in capsys.readouterr().err


def test_subir_com_api_ja_rodando(amb: Ambiente, capsys: pytest.CaptureFixture[str]) -> None:
    amb.estado_api(env="prd")
    amb.sis.portas.add(8080)  # é a própria API
    assert amb.executar("subir") == 0
    assert amb.sis.iniciados == []
    assert "A API já está rodando" in capsys.readouterr().out
    assert amb.executar("subir", "--tst") == 2  # outro ambiente: manda usar reiniciar/parar
    assert amb.sis.iniciados == []


def test_subir_falha_se_o_banco_nao_fica_saudavel(amb: Ambiente) -> None:
    amb.sis.quando("docker", "inspect", saida="running|starting\n")
    assert amb.executar("subir", "--tst") == 1
    assert amb.sis.iniciados == []


def test_subir_falha_se_o_docker_esta_fechado(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.sis.quando("docker", "compose", codigo=1, saida="error during connect")
    assert amb.executar("subir", "--tst") == 1
    assert "Docker Desktop" in capsys.readouterr().err
    assert amb.sis.iniciados == []


def test_subir_encerra_a_api_que_nao_responde(amb: Ambiente) -> None:
    amb.frontend_em_dia()
    amb.sis.api_ok = False
    assert amb.executar("subir", "--tst") == 1
    assert amb.sis.encerrados == [4242]
    assert not (amb.estado / "api.pid").exists()


def test_log_da_api_que_morreu_sai_filtrado(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.frontend_em_dia()
    amb.sis.log_inicial = "Traceback\nerro postgresql://app:MARC_SENHA_5@127.0.0.1:5433/prd\n"
    amb.sis.api_ok = False
    original = amb.sis.processo_vivo
    chamadas = {"n": 0}

    def morre_logo(pid: int) -> bool:
        chamadas["n"] += 1
        return original(pid) and chamadas["n"] < 2

    amb.sis.processo_vivo = morre_logo  # type: ignore[method-assign]
    assert amb.executar("subir", "--tst") == 1
    erro = capsys.readouterr().err
    assert "MARC_SENHA_" not in erro
    assert "<url oculta>" in erro


# ------------------------------------------------------------------ parar (AC-4)


def test_parar_encerra_so_o_pid_guardado(amb: Ambiente) -> None:
    amb.estado_api(pid=111)
    amb.sis.vivos.add(222)  # outro processo qualquer: não pode ser tocado
    amb.sis.linhas[222] = "outro.exe"
    assert amb.executar("parar") == 0
    assert amb.sis.encerrados == [111]
    assert not (amb.estado / "api.pid").exists()
    assert 222 in amb.sis.vivos
    assert not any(c[0][0] == "docker" for c in amb.sis.comandos)  # o banco continua


def test_parar_recusa_pid_que_nao_e_do_abako(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.estado_api(pid=111)
    amb.sis.linhas[111] = r"C:\Windows\notepad.exe"  # PID reaproveitado por outro programa
    assert amb.executar("parar") == 2
    assert amb.sis.encerrados == []
    assert not (
        amb.estado / "api.pid"
    ).exists()  # o arquivo velho não deve bloquear o próximo subir
    assert "outro programa" in capsys.readouterr().err


def test_parar_sem_arquivo_ou_com_processo_morto_nao_encerra_nada(amb: Ambiente) -> None:
    assert amb.executar("parar") == 0
    amb.estado_api(pid=111)
    amb.sis.vivos.discard(111)
    assert amb.executar("parar") == 0
    assert amb.sis.encerrados == []
    assert not (amb.estado / "api.pid").exists()


def test_reiniciar_mantem_o_ambiente(amb: Ambiente) -> None:
    amb.frontend_em_dia()
    amb.estado_api(pid=111, env="tst")
    assert amb.executar("reiniciar") == 0
    assert amb.sis.encerrados == [111]
    ((_, env, _),) = amb.sis.iniciados
    assert env == {"ABAKO_ENV": "tst"}


# ------------------------------------------------------------------ status (AC-3)


def _status_completo(amb: Ambiente) -> None:
    amb.frontend_em_dia()
    amb.backup_prd("abako-prd-20261110-080000.dump.age")
    amb.estado_api(env="prd")
    amb.sis.portas.add(8080)
    # as saídas trazem lixo sintético com senha: nada disso pode chegar ao terminal
    amb.sis.quando("docker", "inspect", saida="running|healthy\n")
    amb.sis.quando("alembic", "heads", saida="0014 (head)\n")
    amb.sis.quando(
        "alembic",
        "current",
        alvo="tst",
        saida="postgresql://u:MARC_SENHA_1@127.0.0.1:5433/tst\n0013\n",
    )
    amb.sis.quando("git", "branch", saida="feat/x\n")
    amb.sis.quando("git", "rev-list", saida="3\n")


def test_status_mostra_tudo_e_nenhum_segredo(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    _status_completo(amb)
    assert amb.executar("status") == 0
    saida = capsys.readouterr().out
    assert "Banco (contêiner): de pé e saudável" in saida
    assert "rodando em http://127.0.0.1:8080 (PID 4242), AMBIENTE: PRD (dados reais)" in saida
    assert "Migrações tst: 0013 (o repositório está em 0014: PENDENTE)" in saida
    assert "Migrações prd: não consultadas" in saida
    assert (
        "há 10 dias e 4 horas (abako-prd-20261110-080000.dump.age) [ANTIGO: mais de 7 dias]"
        in saida
    )
    assert "Build do front: em dia" in saida
    assert "branch feat/x, 3 commit(s) atrás de origin/main" in saida
    assert "MARC_SENHA_" not in saida
    assert not RE_URL_COM_CREDENCIAL.search(saida)
    # status sem --prd nunca fala com o prd
    assert not any(e.get("ABAKO_ENV") == "prd" for _, e, _ in amb.sis.comandos)


def test_status_mostra_build_desatualizado_e_api_parada(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    assert amb.executar("status") == 0
    saida = capsys.readouterr().out
    assert "Build do front: DESATUALIZADO (dist ausente" in saida
    assert "API: parada (porta 8080 livre)" in saida


def test_status_nao_vaza_a_mensagem_de_excecao(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.sis.explodir_em = ("docker", "inspect")
    assert amb.executar("status") == 0
    saida = capsys.readouterr()
    assert "RuntimeError" in saida.out
    assert "MARC_SENHA_" not in saida.out + saida.err


def test_excecao_inesperada_sai_so_com_a_classe(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.sis.explodir_em = ("docker", "compose")
    assert amb.executar("subir", "--tst") == 1
    err = capsys.readouterr().err
    assert "RuntimeError" in err
    assert "MARC_SENHA_" not in err


def test_status_prd_exige_confirmacao_e_terminal(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.sis.terminal = False
    assert amb.executar("status", "--prd") == 0
    assert "Migrações prd: indisponível" in capsys.readouterr().out
    assert amb.sis.confirmacoes_do_prd() == []
    amb.sis.terminal = True
    amb.sis.digitado = ["PRD"]
    amb.sis.quando("alembic", "heads", saida="0014 (head)\n")
    amb.sis.quando("alembic", "current", alvo="prd", saida="0014 (head)\n")
    assert amb.executar("status", "--prd") == 0
    assert "Migrações prd: 0014 (em dia com o repositório)" in capsys.readouterr().out
    assert len(amb.sis.confirmacoes_do_prd()) == 1


# ------------------------------------------------------------------ prd: confirmação (AC-6)


@pytest.mark.parametrize(
    "argv",
    [
        ("backup", "--alvo", "prd"),
        ("migrar", "--alvo", "prd"),
        ("pipeline", "--alvo", "prd"),
        ("atualizar",),
    ],
)
def test_operacao_no_prd_sem_terminal_e_recusada_sem_executar_nada(
    amb: Ambiente, argv: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    amb.sis.terminal = False
    amb.sis.digitado = ["PRD"]  # mesmo que algo tentasse responder, não há terminal
    assert amb.executar(*argv) == 2
    assert amb.sis.comandos == []
    assert amb.sis.perguntas == []
    assert "terminal interativo" in capsys.readouterr().err


@pytest.mark.parametrize("resposta", ["", "sim", "prd", "tst", "PRD2"])
@pytest.mark.parametrize("argv", [("backup", "--alvo", "prd"), ("pipeline", "--alvo", "prd")])
def test_confirmacao_digitada_errada_recusa(
    amb: Ambiente, argv: tuple[str, ...], resposta: str
) -> None:
    amb.sis.digitado = [resposta]
    assert amb.executar(*argv) == 2
    assert amb.sis.comandos == []


def test_confirmacao_do_prd_so_vai_ao_ambiente_do_filho(amb: Ambiente) -> None:
    amb.sis.digitado = ["PRD"]
    amb.sis.quando("scripts.backup", saida="backup: abako-prd-20261120-120000.dump.age\n")
    assert amb.executar("backup", "--alvo", "prd") == 0
    ((cmd, env, _),) = amb.sis.comandos
    assert cmd == [PY, "-m", "scripts.backup", "--alvo", "prd"]
    assert env == {"ABAKO_ENV": "prd", VAR_CONFIRMA_PRD: "sim"}
    assert VAR_CONFIRMA_PRD not in os.environ  # o processo pai nunca a recebe


def test_backup_tst_nao_pede_confirmacao_nem_leva_a_variavel(amb: Ambiente) -> None:
    assert amb.executar("backup") == 0  # padrão: tst
    assert amb.sis.perguntas == []
    assert amb.sis.comandos[0][1] == {"ABAKO_ENV": "tst"}


def test_pipeline_codigos_do_filho(amb: Ambiente) -> None:
    amb.sis.quando("pipeline", codigo=3)
    assert amb.executar("pipeline") == 1  # trava ocupada vira falha
    amb.sis.regras.clear()
    amb.sis.quando("pipeline", codigo=2)
    assert amb.executar("pipeline") == 2
    amb.sis.regras.clear()
    assert amb.executar("pipeline", "--alvo", "tst") == 0
    assert amb.sis.comandos[-1][0] == [PY, "-m", "pipeline", "--alvo", "tst"]


# ------------------------------------------------------------------ migrar e atualizar (AC-5, AC-6)


def _migracao_pendente(amb: Ambiente, alvo: str = "prd") -> None:
    amb.sis.quando("alembic", "heads", saida="0014 (head)\n")
    amb.sis.quando("alembic", "current", alvo=alvo, saida="0013\n")
    amb.sis.quando("alembic", "history", saida="0013 -> 0014 (head), leituras do pipeline\n")


def test_atualizar_recusa_arvore_suja(amb: Ambiente) -> None:
    amb.sis.quando("git", "status", "--porcelain", saida=" M backend/app.py\n")
    amb.sis.quando("git", "branch", saida="main\n")
    assert amb.executar("atualizar") == 2
    assert not any("fetch" in r or "pull" in r for r in amb.sis.rotulos())
    assert amb.sis.perguntas == []


def test_atualizar_recusa_branch_fora_da_main(amb: Ambiente) -> None:
    amb.git_limpo_na_main("feat/x")
    assert amb.executar("atualizar") == 2
    assert not any("fetch" in r or "pull" in r for r in amb.sis.rotulos())


def test_atualizar_com_migracao_pendente_segue_a_ordem_e_migra_a_revisao_exata(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.git_limpo_na_main()
    _migracao_pendente(amb)
    amb.backup_prd("abako-prd-20261118-100000.dump.age")  # 2 dias e 2 horas
    (amb.raiz / "frontend" / "node_modules").mkdir()  # sem dist: só npm run build
    amb.sis.digitado = ["PRD", "MIGRAR"]
    assert amb.executar("atualizar") == 0
    assert amb.sis.rotulos() == [
        "git status --porcelain",
        "git branch --show-current",
        "git fetch",
        "git pull --ff-only",
        "-m alembic heads",
        "-m alembic current",
        "-m alembic history -r 0013:0014",
        "-m scripts.config_local",
        "-m alembic upgrade 0014",
        "npm run build",
    ]
    assert "PRD" in amb.sis.perguntas[0] and "MIGRAR" in amb.sis.perguntas[1]
    upgrade = next(c for c in amb.sis.comandos if "upgrade" in c[0])
    assert upgrade[1] == {"ABAKO_ENV": "prd", VAR_CONFIRMA_PRD: "sim"}
    # a confirmação só chega aos comandos do alembic do prd (current e upgrade)
    assert len(amb.sis.confirmacoes_do_prd()) == 2
    saida = capsys.readouterr().out
    assert "0014: leituras do pipeline" in saida


def test_atualizar_sem_backup_recente_recusa_antes_de_migrar(amb: Ambiente) -> None:
    amb.git_limpo_na_main()
    _migracao_pendente(amb)
    amb.backup_prd("abako-prd-20261110-080000.dump.age")  # 10 dias
    amb.sis.digitado = ["PRD", "MIGRAR"]
    assert amb.executar("atualizar") == 2
    assert not any("upgrade" in r for r in amb.sis.rotulos())
    assert len(amb.sis.perguntas) == 1  # nem chegou ao pedido de MIGRAR


def test_atualizar_sem_confirmacao_de_migrar_nao_migra(amb: Ambiente) -> None:
    amb.git_limpo_na_main()
    _migracao_pendente(amb)
    amb.backup_prd("abako-prd-20261118-100000.dump.age")
    amb.sis.digitado = ["PRD", "migrar"]
    assert amb.executar("atualizar") == 2
    assert not any("upgrade" in r for r in amb.sis.rotulos())


def test_atualizar_sem_confirmacao_inicial_nao_puxa_nada(amb: Ambiente) -> None:
    amb.git_limpo_na_main()
    amb.sis.digitado = ["n"]
    assert amb.executar("atualizar") == 2
    assert not any("pull" in r for r in amb.sis.rotulos())
    assert amb.sis.confirmacoes_do_prd() == []


def test_atualizar_reinicia_a_api_que_estava_rodando(amb: Ambiente) -> None:
    amb.git_limpo_na_main()
    amb.frontend_em_dia()
    amb.estado_api(pid=111, env="prd")
    amb.sis.quando("alembic", "heads", saida="0014 (head)\n")
    amb.sis.quando("alembic", "current", alvo="prd", saida="0014 (head)\n")
    amb.sis.digitado = ["PRD"]
    assert amb.executar("atualizar") == 0
    assert amb.sis.encerrados == [111]
    ((_, env, _),) = amb.sis.iniciados
    assert env == {"ABAKO_ENV": "prd"}
    assert not any("upgrade" in r for r in amb.sis.rotulos())  # nada pendente
    assert not any("npm" in r for r in amb.sis.rotulos())  # build em dia


def test_pull_so_fast_forward_e_falha_vira_codigo_1(amb: Ambiente) -> None:
    amb.git_limpo_na_main()
    amb.sis.quando("git", "pull", codigo=1, saida="fatal: Not possible to fast-forward")
    amb.sis.digitado = ["PRD"]
    assert amb.executar("atualizar") == 1
    pull = [c for c, _, _ in amb.sis.comandos if "pull" in c]
    assert pull == [["git", "pull", "--ff-only"]]


def test_migrar_tst_na_main_usa_a_revisao_exata_sem_confirmacao(amb: Ambiente) -> None:
    amb.git_limpo_na_main()
    _migracao_pendente(amb, alvo="tst")
    assert amb.executar("migrar") == 0
    upgrade = next(c for c in amb.sis.comandos if "upgrade" in c[0])
    assert upgrade[0] == [PY, "-m", "alembic", "upgrade", "0014"]  # nunca `head` às cegas
    assert upgrade[1] == {"ABAKO_ENV": "tst"}
    assert amb.sis.perguntas == []


def test_migrar_prd_fora_da_main_recusa(amb: Ambiente) -> None:
    amb.git_limpo_na_main("feat/x")
    assert amb.executar("migrar", "--alvo", "prd") == 2
    assert not any("alembic" in r for r in amb.sis.rotulos())
    assert amb.sis.perguntas == []  # recusou antes de pedir a confirmação


def test_migrar_tst_fora_da_main_avisa_a_branch_e_migra(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.git_limpo_na_main("feat/x")  # uma migração nasce numa branch e é testada no tst
    _migracao_pendente(amb, alvo="tst")
    assert amb.executar("migrar") == 0
    assert "Branch atual: feat/x" in capsys.readouterr().out
    assert any(r == "-m alembic upgrade 0014" for r in amb.sis.rotulos())
    assert amb.sis.perguntas == []


def test_migrar_recusa_mais_de_uma_cabeca(amb: Ambiente) -> None:
    amb.git_limpo_na_main()
    amb.sis.quando("alembic", "heads", saida="0014 (head)\n0015 (head)\n")
    assert amb.executar("migrar") == 2
    assert not any("upgrade" in r for r in amb.sis.rotulos())


def test_migrar_prd_exige_backup_e_confirmacao(amb: Ambiente) -> None:
    amb.git_limpo_na_main()
    _migracao_pendente(amb)
    amb.sis.digitado = ["PRD", "MIGRAR"]
    assert amb.executar("migrar", "--alvo", "prd") == 2  # sem nenhum backup do prd
    assert not any("upgrade" in r for r in amb.sis.rotulos())
    amb.backup_prd("abako-prd-20261120-090000.dump.age")
    amb.sis.digitado = ["PRD", "MIGRAR"]
    assert amb.executar("migrar", "--alvo", "prd") == 0
    assert any(r == "-m alembic upgrade 0014" for r in amb.sis.rotulos())


# ------------------------------------------------------------------ demais subcomandos


def test_check_usa_com_banco_e_avisa_da_demora(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    assert amb.executar("check") == 0
    ((cmd, _, capturar),) = amb.sis.comandos
    assert cmd == [PY, "-m", "scripts.check", "--com-banco"]
    assert capturar is False
    assert "10 minutos" in capsys.readouterr().out
    amb.sis.quando("scripts.check", codigo=1)
    assert amb.executar("check") == 1


def test_abrir_so_com_a_api_de_pe(amb: Ambiente) -> None:
    assert amb.executar("abrir") == 1
    assert amb.sis.url_aberta == []
    amb.estado_api()
    amb.sis.portas.add(8080)
    assert amb.executar("abrir") == 0
    assert amb.sis.url_aberta == ["http://127.0.0.1:8080"]


def test_ajuda_lista_todos_os_subcomandos(capsys: pytest.CaptureFixture[str]) -> None:
    assert operacao.main(["ajuda"]) == 0
    saida = capsys.readouterr().out
    for nome in (
        "ajuda",
        "status",
        "subir",
        "parar",
        "reiniciar",
        "build",
        "atualizar",
        "backup",
        "migrar",
        "pipeline",
        "check",
        "abrir",
    ):
        assert re.search(rf"^\s+{nome}\b", saida, re.MULTILINE), nome
    assert operacao.main([]) == 0


def test_codigos_de_saida_subcomando_invalido_e_alvo_invalido() -> None:
    assert operacao.main(["xyz"]) == 2
    assert operacao.main(["backup", "--alvo", "restauracao"]) == 2


def test_build_roda_npm_ci_so_sem_node_modules(amb: Ambiente) -> None:
    assert amb.executar("build") == 0
    assert amb.sis.rotulos() == ["npm ci", "npm run build"]
    amb.sis.comandos.clear()
    (amb.raiz / "frontend" / "node_modules").mkdir()
    assert amb.executar("build") == 0
    assert amb.sis.rotulos() == ["npm run build"]
    amb.sis.quando("npm", "run", codigo=1)
    assert amb.executar("build") == 1


# ------------------------------------------------------------------ AC-7: segredo e .env


def test_o_script_nao_le_o_arquivo_de_variaveis() -> None:
    raiz = Path(operacao.__file__).resolve().parent
    for arq in ("operacao.py", "abako.ps1"):
        texto = (raiz / arq).read_text(encoding="utf-8-sig")
        assert not re.search(r"""["']\.env["']|carregar_env|dotenv|\\\.env\b""", texto), arq
    codigo = (raiz / "operacao.py").read_text(encoding="utf-8")
    assert "os.environ[" not in codigo and "putenv" not in codigo
    assert "ABAKO_CONFIRMA_PRD" not in codigo.replace("VAR_CONFIRMA_PRD", "")  # só pela constante


def test_o_fonte_nao_traz_senha_nem_url_de_conexao() -> None:
    codigo = Path(operacao.__file__).read_text(encoding="utf-8")
    assert not RE_URL_COM_CREDENCIAL.search(codigo)
    assert "print(r.saida" not in codigo  # saída de filho só passa por saida_segura


def test_saida_de_falha_do_filho_sai_filtrada(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.sis.digitado = ["PRD"]
    amb.sis.quando(
        "scripts.backup",
        codigo=2,
        saida=(
            "backup RECUSADO: postgresql://app:MARC_SENHA_4@127.0.0.1:5433/prd "
            "password=MARC_SENHA_5\n"
        ),
    )
    assert amb.executar("backup", "--alvo", "prd") == 2
    saida = capsys.readouterr()
    assert "MARC_SENHA_" not in saida.out + saida.err


# ------------------------------------------------------------ módulos auxiliares e sistema real


def test_config_local_devolve_so_conteiner_e_pasta(tmp_path: Path) -> None:
    from scripts.config_local import coletar

    pasta = tmp_path / "bk"
    ok = coletar({"COMPOSE_PROJECT_NAME": "abk", "ABAKO_BACKUP_DIR": str(pasta), "X": "y"})
    assert ok == {"conteiner": "abk-postgres", "pasta": str(pasta.resolve()), "porta": 8080}
    assert coletar({}) == {"porta": 8080}
    assert coletar({"ABAKO_BACKUP_DIR": "relativa"}) == {"porta": 8080}
    assert coletar({"ABAKO_PORTA": "9090"}) == {"porta": 9090}
    assert coletar({"ABAKO_PORTA": "99999"}) == {"porta_invalida": "sim"}  # sem repetir o valor


def test_pasta_de_estado_fica_fora_do_repositorio(tmp_path: Path) -> None:
    assert (
        operacao.pasta_estado_padrao({"LOCALAPPDATA": str(tmp_path)})
        == (tmp_path / "abako").resolve()
    )
    from db.alvo import RAIZ

    with pytest.raises(Falha):
        operacao.pasta_estado_padrao({"LOCALAPPDATA": str(RAIZ)})


def test_sistema_real_inicia_consulta_e_encerra_so_o_proprio_filho(tmp_path: Path) -> None:
    sistema = SistemaReal()
    pasta = tmp_path / "João Pedro"  # acento e espaço, como o perfil do usuário
    pasta.mkdir()
    log = pasta / "filho.log"
    pid = sistema.iniciar_em_segundo_plano(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        cwd=pasta,
        env_extra={},
        log=log,
    )
    try:
        assert sistema.processo_vivo(pid)
        assert not e_processo_do_abako(sistema.linha_de_comando(pid))  # não é `-m backend`
        assert sistema.processo_vivo(os.getpid())  # o próprio pytest segue vivo
        sistema.encerrar(pid)
        for _ in range(50):
            if not sistema.processo_vivo(pid):
                break
            sistema.dormir(0.2)
        assert not sistema.processo_vivo(pid)
    finally:
        if sistema.processo_vivo(pid):
            sistema.encerrar(pid)
    assert sistema.processo_vivo(os.getpid())


def test_sistema_real_recusa_encerrar_o_proprio_processo() -> None:
    with pytest.raises(Falha):
        SistemaReal().encerrar(os.getpid())
    with pytest.raises(Falha):
        SistemaReal().encerrar(0)


def test_sistema_real_porta_e_api_responde() -> None:
    sistema = SistemaReal()

    class Resposta(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(404)
            self.end_headers()

        def log_message(self, *args: object) -> None:
            return None

    servidor = HTTPServer(("127.0.0.1", 0), Resposta)
    porta = servidor.server_address[1]
    fio = threading.Thread(target=servidor.serve_forever, daemon=True)
    fio.start()
    try:
        assert sistema.porta_ocupada(porta)
        assert sistema.api_responde(porta)  # 404 também prova que há uma API respondendo
    finally:
        servidor.shutdown()
        servidor.server_close()
    livre = socket.socket()
    livre.bind(("127.0.0.1", 0))
    porta_livre = livre.getsockname()[1]
    livre.close()
    assert not sistema.porta_ocupada(porta_livre)
    assert not sistema.api_responde(porta_livre)


def test_sistema_real_roda_comando_e_remove_a_confirmacao_herdada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(VAR_CONFIRMA_PRD, "sim")  # simula um terminal com a variável já posta
    codigo = (
        "import os; print(os.environ.get('ABAKO_CONFIRMA_PRD', 'ausente'), "
        "os.environ.get('MARCA', '-'))"
    )
    r = SistemaReal().rodar([sys.executable, "-c", codigo], env_extra={"MARCA": "x"})
    assert r.codigo == 0 and r.saida.split() == ["ausente", "x"]
    r = SistemaReal().rodar(
        [sys.executable, "-c", codigo], env_extra={VAR_CONFIRMA_PRD: "sim", "MARCA": "y"}
    )
    assert r.saida.split() == ["sim", "y"]


# ------------------------------------------------------------------ revisão: porta, PID, backup


@pytest.mark.parametrize("valor", ["abc", "0", "65536", "-1", "80 80", "8080.5", "٨٠", "1e3"])
def test_porta_invalida_e_recusada(valor: str) -> None:
    with pytest.raises(ValueError, match="1 a 65535"):
        porta_valida(valor)


@pytest.mark.parametrize(
    ("valor", "esperada"),
    [(None, 8080), ("", 8080), ("   ", 8080), ("1", 1), ("65535", 65535), (" 9090 ", 9090)],
)
def test_porta_valida_vazia_e_padrao_e_faixa_aceita(valor: str | None, esperada: int) -> None:
    assert porta_valida(valor) == esperada


def test_porta_vem_da_configuracao_do_projeto(amb: Ambiente) -> None:
    amb.sis.quando(
        "scripts.config_local",
        saida=json.dumps({"conteiner": "c", "pasta": str(amb.backups), "porta": 9191}),
    )
    op = Operador(amb.sis, amb.raiz, amb.estado, python=PY)
    assert op.porta == 9191
    assert op.url == "http://127.0.0.1:9191"


def test_porta_do_terminal_sobrescreve_a_da_configuracao(amb: Ambiente) -> None:
    amb.sis.quando("scripts.config_local", saida=json.dumps({"porta": 9191}))
    assert operacao._porta_do_terminal({"ABAKO_PORTA": "7000"}) == 7000
    assert operacao._porta_do_terminal({"ABAKO_PORTA": ""}) is None
    assert operacao._porta_do_terminal({}) is None
    op = Operador(amb.sis, amb.raiz, amb.estado, porta=7000, python=PY)
    assert op.porta == 7000
    assert not any("config_local" in r for r in amb.sis.rotulos())  # nem consultou o projeto


def test_porta_invalida_no_terminal_falha_com_mensagem_clara(
    amb: Ambiente, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for valor in ("abc", "0", "70000"):
        monkeypatch.setenv("ABAKO_PORTA", valor)
        assert amb.executar("status") == 1
        err = capsys.readouterr().err
        assert "ABAKO_PORTA inválida" in err and "1 a 65535" in err
    assert amb.sis.comandos == []


def test_porta_invalida_na_configuracao_do_projeto_falha_sem_subir_nada(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.sis.quando("scripts.config_local", saida=json.dumps({"porta_invalida": "sim"}))
    assert amb.executar("subir", "--tst") == 1
    assert "ABAKO_PORTA inválida" in capsys.readouterr().err
    assert not any(r.startswith("docker") for r in amb.sis.rotulos())
    assert amb.sis.iniciados == []


def test_parar_sem_conseguir_ler_a_linha_mantem_o_pid(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.estado_api(pid=111)
    del amb.sis.linhas[111]  # PowerShell falhou ou demorou: o processo vive, a linha não veio
    assert amb.executar("parar") == 2
    err = capsys.readouterr().err
    assert "não consegui conferir" in err
    assert "outro programa" not in err
    assert amb.sis.encerrados == []
    assert (amb.estado / "api.pid").exists()


def test_subir_sem_conseguir_ler_a_linha_do_pid_guardado_mantem_o_pid(amb: Ambiente) -> None:
    amb.estado_api(pid=111)
    del amb.sis.linhas[111]
    assert amb.executar("subir", "--tst") == 2
    assert (amb.estado / "api.pid").exists()
    assert amb.sis.iniciados == []
    assert not any(r.startswith("docker") for r in amb.sis.rotulos())


def test_atualizar_com_backup_velho_diz_que_o_codigo_ja_foi_atualizado(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.git_limpo_na_main()
    _migracao_pendente(amb)
    amb.backup_prd("abako-prd-20261110-080000.dump.age")  # 10 dias
    amb.sis.digitado = ["PRD", "MIGRAR"]
    assert amb.executar("atualizar") == 2
    err = capsys.readouterr().err
    assert "código já foi atualizado (git pull feito)" in err
    assert "depois do backup rode `abako atualizar` de novo" in err
    assert "git pull --ff-only" in amb.sis.rotulos()  # o pull de fato aconteceu antes


def test_migrar_prd_com_backup_velho_nao_fala_em_pull(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.git_limpo_na_main()
    _migracao_pendente(amb)
    amb.backup_prd("abako-prd-20261110-080000.dump.age")
    amb.sis.digitado = ["PRD", "MIGRAR"]
    assert amb.executar("migrar", "--alvo", "prd") == 2
    err = capsys.readouterr().err
    assert "abako backup --alvo prd" in err and "pull" not in err


def test_backup_de_tamanho_zero_nao_conta(amb: Ambiente) -> None:
    (amb.backups / "abako-prd-20261120-110000.dump.age").write_bytes(b"")  # nome recente, vazio
    with pytest.raises(Recusa, match="não há backup do prd"):
        amb.op.exigir_backup_recente()
    amb.backup_prd("abako-prd-20261119-110000.dump.age")  # 1 dia e 1 hora, com conteúdo
    amb.op.exigir_backup_recente()  # o vazio, mais novo, é ignorado


def test_status_ignora_backup_vazio(amb: Ambiente, capsys: pytest.CaptureFixture[str]) -> None:
    (amb.backups / "abako-prd-20261120-110000.dump.age").write_bytes(b"")
    assert amb.executar("status") == 0
    assert "Último backup do prd: nenhum encontrado" in capsys.readouterr().out


def test_procurar_executavel_ignora_a_raiz_do_repositorio_e_a_pasta_atual(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    plantado = repo / "bin"
    bom = tmp_path / "bin"
    for pasta in (plantado, bom):
        pasta.mkdir(parents=True)
        exe = pasta / "ferr.exe"
        exe.write_bytes(b"x")
        exe.chmod(0o755)
    path = os.pathsep.join([str(plantado), ".", "", str(bom)])
    assert procurar_executavel("ferr.exe", repo, path) == str(bom.resolve() / "ferr.exe")
    assert procurar_executavel("ferr.exe", repo, str(plantado)) is None  # só havia o plantado
    assert procurar_executavel("inexistente.exe", repo, path) is None
    assert procurar_executavel(r"C:\x\y.exe", repo, "") == r"C:\x\y.exe"  # com caminho: como veio
    if sys.platform == "win32":  # sem extensão, vale o PATHEXT
        assert procurar_executavel("ferr", repo, path, ".COM;.EXE") == str(
            bom.resolve() / "ferr.exe"
        )


def test_sistema_real_nao_executa_programa_plantado_no_repositorio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    plantado = repo / "bin"
    bom = tmp_path / "bin"
    for pasta in (plantado, bom):
        pasta.mkdir(parents=True)
        exe = pasta / "ferr.exe"
        exe.write_bytes(b"x")
        exe.chmod(0o755)
    monkeypatch.setattr(operacao, "RAIZ", repo)
    monkeypatch.setenv("PATH", os.pathsep.join([str(plantado), str(bom)]))
    assert SistemaReal._exe("ferr.exe") == str(bom.resolve() / "ferr.exe")
    with pytest.raises(Falha, match="programa não encontrado"):
        SistemaReal().rodar(["nao-existe-no-path.exe"])


def test_abrir_recusa_porta_ocupada_por_outro_programa(
    amb: Ambiente, capsys: pytest.CaptureFixture[str]
) -> None:
    amb.sis.portas.add(8080)  # alguém usa a porta, mas não é a API do abako
    assert amb.executar("abrir") == 2
    assert amb.sis.url_aberta == []
    assert "outro programa" in capsys.readouterr().err


def test_erros_de_uso_saem_em_portugues_com_codigo_2(capsys: pytest.CaptureFixture[str]) -> None:
    casos = [
        (["xyz"], "subcomando desconhecido: 'xyz'"),
        (["backup", "--alvo", "restauracao"], "valor inválido para --alvo: 'restauracao'"),
        (["parar", "extra"], "argumentos não reconhecidos: extra"),
        (["backup", "--alvo"], "uso inválido"),
    ]
    for argv, esperado in casos:
        assert operacao.main(argv) == 2, argv
        err = capsys.readouterr().err
        assert esperado in err, argv
        assert "abako ajuda" in err
        assert not re.search(r"invalid|choose|expected|unrecognized", err), argv
    assert operacao.main(["--help"]) == 0


def test_estado_da_api_em_pasta_com_acento_e_espaco(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    perfil = tmp_path / "João Pedro"
    assert (
        operacao.pasta_estado_padrao({"LOCALAPPDATA": str(perfil)}) == (perfil / "abako").resolve()
    )
    amb = Ambiente(tmp_path, SistemaFalso())
    amb.estado = perfil / "abako"
    amb.frontend_em_dia()
    assert amb.executar("subir", "--tst") == 0
    assert (perfil / "abako" / "api.pid").is_file()
    assert (perfil / "abako" / "api.log").is_file()
    assert amb.executar("parar") == 0
    assert not (perfil / "abako" / "api.pid").exists()
    assert "João Pedro" in capsys.readouterr().out  # o caminho do log sai íntegro


def test_documentacao_de_uso_existe_e_explica_os_termos_de_web() -> None:
    doc = Path(operacao.__file__).resolve().parent.parent / "docs" / "operacao"
    texto = (doc / "subir-e-atualizar.md").read_text(encoding="utf-8")
    for termo in (
        "abako subir",
        "build",
        "dist",
        "PWA",
        "cache",
        "Service Workers",
        "Unregister",
        "abako parar",
        "abako atualizar",
        "abako backup",
        "abako migrar",
        "PRD",
        "ABAKO_PORTA",
        "1 a 65535",
        "Aspas duplas",
        "tamanho",
    ):
        assert termo in texto, termo
    assert "7 dias" in texto
