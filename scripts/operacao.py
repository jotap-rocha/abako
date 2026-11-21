r"""Operação local do abako num comando só (ADR 056, SPEC-015).

Uso, na raiz do repositório (o invólucro `scripts\abako.ps1` faz isto por você):

    .venv\Scripts\python.exe -m scripts.operacao <subcomando>

Subcomandos: ajuda, status, subir, parar, reiniciar, build, atualizar, backup, migrar,
pipeline, check, abrir, raiz. Veja `ajuda` e `docs/operacao/subir-e-atualizar.md`.

Desenho:

- A lógica é Python; tudo o que toca o sistema (processos, rede, terminal, relógio) passa por um
  objeto `Sistema` injetável. Os testes usam um `Sistema` falso: nenhum Docker real e nunca o prd.
- Este script **nunca abre o arquivo de variáveis**. Só os módulos do projeto o carregam, cada um
  no seu processo (o nome do contêiner e a pasta de backups vêm de `scripts.config_local`).
- Operação no `prd` só com confirmação **digitada por uma pessoa** num terminal interativo; sem
  terminal, recusa. A variável de confirmação só existe no ambiente do processo FILHO, depois
  da confirmação, e é removida de qualquer ambiente herdado (`ambiente_filho`).
- Saída, log e erro nunca levam senha, URL de conexão nem valor financeiro (`saida_segura`,
  `descrever_excecao`).

Códigos de saída: 0 ok; 1 falha; 2 recusado por regra ou segurança.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import NoReturn, Protocol
from urllib import error, request

from db.alvo import RAIZ, VAR_CONFIRMA_PRD, AlvoInvalido
from db.conteiner import MARCAS_PERIGOSAS, pasta_fora_do_repo
from db.retencao import FUSO, ler_nome
from scripts.config_local import VAR_PORTA, porta_valida

OK = 0
FALHA = 1
RECUSADO = 2

AMBIENTES = ("tst", "prd")
LIMITE_BACKUP = timedelta(days=7)
ESPERA_BANCO_S = 120
ESPERA_API_S = 30
ESPERA_ENCERRAR_S = 10
MSG_PORTA_INVALIDA = "ABAKO_PORTA inválida: use um número de 1 a 65535 (ou deixe vazia: 8080)"
MSG_NAO_CONFERI = "não consegui conferir o processo guardado (PID mantido); tente de novo"
PALAVRA_ACESSO = "PRD"
PALAVRA_MIGRAR = "MIGRAR"


class Recusa(Exception):
    """A regra de segurança ou de processo impede a operação (código 2)."""


class Falha(Exception):
    """A operação foi tentada e falhou (código 1)."""


@dataclass(frozen=True)
class Resultado:
    codigo: int
    saida: str = ""


@dataclass(frozen=True)
class Estado:
    """O que o `subir` guarda para o `parar` e o `status` (arquivo fora do repositório)."""

    pid: int
    env: str
    porta: int


class Sistema(Protocol):
    """Tudo o que toca o sistema operacional; os testes trocam por um falso."""

    def rodar(
        self,
        cmd: Sequence[str],
        *,
        cwd: Path | None = None,
        env_extra: Mapping[str, str] | None = None,
        capturar: bool = True,
    ) -> Resultado: ...

    def iniciar_em_segundo_plano(
        self, cmd: Sequence[str], *, cwd: Path, env_extra: Mapping[str, str], log: Path
    ) -> int: ...

    def processo_vivo(self, pid: int) -> bool: ...

    def linha_de_comando(self, pid: int) -> str | None: ...

    def encerrar(self, pid: int) -> None: ...

    def porta_ocupada(self, porta: int) -> bool: ...

    def api_responde(self, porta: int) -> bool: ...

    def tem_terminal(self) -> bool: ...

    def pedir(self, pergunta: str) -> str: ...

    def agora(self) -> datetime: ...

    def dormir(self, segundos: float) -> None: ...

    def abrir_url(self, url: str) -> None: ...


# --------------------------------------------------------------------------------------
# Funções puras (sem efeito colateral; testadas com valores escritos à mão)
# --------------------------------------------------------------------------------------


def normalizar_drive(caminho: str) -> str:
    r"""`d:\projetos\abako` -> `D:\projetos\abako`. Com a letra em minúsculo o Vitest carrega
    módulos duplicados e falha (ver docs/operacao). Caminho sem letra de drive não muda."""
    if len(caminho) >= 2 and caminho[1] == ":" and caminho[0].isalpha():
        return caminho[0].upper() + caminho[1:]
    return caminho


def build_desatualizado(frontend: Path) -> str | None:
    """Motivo do build estar desatualizado, ou `None` se está em dia.

    Desatualizado: `dist/index.html` ausente, ou qualquer arquivo de `src/`, o `package.json`
    ou o `openapi.json` com data de modificação MAIS NOVA que a do `index.html`.
    """
    index = frontend / "dist" / "index.html"
    if not index.is_file():
        return "dist ausente (o front nunca foi construído)"
    referencia = index.stat().st_mtime
    candidatos: list[Path] = [frontend / "package.json", frontend / "openapi.json"]
    src = frontend / "src"
    if src.is_dir():
        candidatos.extend(a for a in src.rglob("*") if a.is_file())
    for arq in candidatos:
        if arq.is_file() and arq.stat().st_mtime > referencia:
            return f"{arq.relative_to(frontend).as_posix()} é mais novo que o dist"
    return None


def ultimo_backup(
    nomes: Sequence[str], ambiente: str, agora: datetime
) -> tuple[str, timedelta] | None:
    """(nome, idade) do backup mais recente do `ambiente`, pela data NO NOME do arquivo.

    Nome fora do padrão `abako-<amb>-AAAAMMDD-HHMMSS.dump.age`, de outro ambiente ou com data no
    futuro é ignorado. `agora` é a hora civil de São Paulo, sem fuso (como os nomes).
    """
    melhor: tuple[datetime, str] | None = None
    for nome in nomes:
        lido = ler_nome(nome)
        if lido is None or lido[0] != ambiente or lido[1] > agora:
            continue
        if melhor is None or lido[1] > melhor[0]:
            melhor = (lido[1], nome)
    if melhor is None:
        return None
    return melhor[1], agora - melhor[0]


def formatar_idade(idade: timedelta) -> str:
    dias, horas = idade.days, idade.seconds // 3600
    return f"{dias} dia{'' if dias == 1 else 's'} e {horas} hora{'' if horas == 1 else 's'}"


def e_processo_do_abako(linha_de_comando: str | None) -> bool:
    """A linha de comando é `python ... -m backend` (a API do abako)?"""
    if not linha_de_comando:
        return False
    baixa = linha_de_comando.lower()
    return "python" in baixa and re.search(r"-m\s+backend(\s|$)", baixa) is not None


def ambiente_filho(
    base: Mapping[str, str], extra: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Ambiente de um processo filho. A confirmação do prd herdada do terminal é REMOVIDA: ela
    só entra via `extra`, depois da confirmação digitada."""
    env = {k: v for k, v in base.items() if k.upper() != VAR_CONFIRMA_PRD}
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.update(extra or {})
    return env


RE_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://\S+")
RE_SENHA = re.compile(r"(?i)\b(password|passwd|pwd|senha|pgpassword)\b\s*[=:]\s*\S+")


def saida_segura(texto: str, max_linhas: int = 15) -> str:
    """Últimas linhas de uma saída de processo, sem URL (com ou sem senha), sem senha e sem as
    linhas que podem carregar conteúdo de linha de tabela (as mesmas de `db.conteiner`)."""
    linhas: list[str] = []
    for bruta in texto.splitlines():
        linha = bruta.rstrip()
        if not linha.strip() or any(m in linha for m in MARCAS_PERIGOSAS):
            continue
        linha = RE_URL.sub("<url oculta>", linha)
        linha = RE_SENHA.sub(r"\1=***", linha)
        linhas.append(linha[:200])
    return "\n".join(linhas[-max_linhas:])


def descrever_excecao(exc: BaseException) -> str:
    """Só a classe e, quando vier do psycopg, o SQLSTATE: a mensagem pode ter URL ou valor."""
    descricao = type(exc).__name__
    sqlstate = getattr(exc, "sqlstate", None)
    if isinstance(sqlstate, str) and re.fullmatch(r"[0-9A-Z]{5}", sqlstate):
        descricao += f" (SQLSTATE {sqlstate})"
    return descricao


RE_REVISAO = re.compile(r"(\w+)(\s+\([^)]*\))?")
RE_HISTORICO = re.compile(r"^\S+\s+->\s+(\w+)(?:\s+\([^)]*\))?,\s*(.*)$")


def revisoes_de(saida: str) -> list[str]:
    """Revisões de `alembic heads|current`: linhas no formato `0014` ou `0014 (head)`."""
    achadas: list[str] = []
    for linha in saida.splitlines():
        m = RE_REVISAO.fullmatch(linha.strip())
        if m:
            achadas.append(m.group(1))
    return achadas


def pendentes_de(saida_historico: str) -> list[tuple[str, str]]:
    """(revisão, descrição) das linhas de `alembic history`, da mais antiga à mais nova."""
    itens: list[tuple[str, str]] = []
    for linha in saida_historico.splitlines():
        m = RE_HISTORICO.match(linha.strip())
        if m:
            itens.append((m.group(1), m.group(2).strip()))
    itens.reverse()
    return itens


def aviso_ambiente(env: str) -> str:
    return "AMBIENTE: PRD (dados reais)" if env == "prd" else "AMBIENTE: TST (banco de teste)"


def procurar_executavel(
    nome: str, raiz: Path, path_env: str, pathext_env: str = ".COM;.EXE;.BAT;.CMD"
) -> str | None:
    """Caminho do executável `nome` nas pastas do PATH, IGNORANDO a pasta atual e qualquer pasta
    dentro do repositório (`raiz`). O `shutil.which` do Windows procura primeiro na pasta atual,
    e um `git.exe` plantado no repositório seria executado no lugar do verdadeiro.

    Nome com caminho (ex.: `sys.executable`) é devolvido como está.
    """
    if os.path.isabs(nome) or "/" in nome or "\\" in nome:
        return nome
    windows = sys.platform == "win32"
    extensoes = [e.lower() for e in pathext_env.split(";") if e]
    if windows and not any(nome.lower().endswith(e) for e in extensoes):
        sufixos = extensoes
    else:
        sufixos = [""]
    raiz = raiz.resolve()
    for bruta in path_env.split(os.pathsep):
        if not bruta or bruta == ".":
            continue
        try:
            pasta = Path(bruta).resolve()
        except OSError:
            continue
        if pasta == raiz or raiz in pasta.parents:
            continue
        for sufixo in sufixos:
            candidato = pasta / (nome + sufixo)
            if candidato.is_file() and (windows or os.access(candidato, os.X_OK)):
                return str(candidato)
    return None


# --------------------------------------------------------------------------------------
# Sistema real
# --------------------------------------------------------------------------------------


class SistemaReal:
    """Implementação de `Sistema` sobre o sistema operacional de verdade."""

    @staticmethod
    def _exe(nome: str) -> str | None:
        return procurar_executavel(
            nome, RAIZ, os.environ.get("PATH", ""), os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD")
        )

    def rodar(
        self,
        cmd: Sequence[str],
        *,
        cwd: Path | None = None,
        env_extra: Mapping[str, str] | None = None,
        capturar: bool = True,
    ) -> Resultado:
        exe = self._exe(cmd[0])
        if exe is None:
            raise Falha(f"programa não encontrado no PATH: {Path(cmd[0]).name!r}")
        env = ambiente_filho(os.environ, env_extra)
        try:
            if capturar:
                r = subprocess.run(
                    [exe, *cmd[1:]],
                    cwd=cwd,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                return Resultado(r.returncode, r.stdout.decode("utf-8", "replace"))
            return Resultado(
                subprocess.run([exe, *cmd[1:]], cwd=cwd, env=env, check=False).returncode
            )
        except OSError as exc:
            raise Falha(
                f"não foi possível executar {Path(cmd[0]).name!r}: {type(exc).__name__}"
            ) from exc

    def iniciar_em_segundo_plano(
        self, cmd: Sequence[str], *, cwd: Path, env_extra: Mapping[str, str], log: Path
    ) -> int:
        # Windows: sem console e fora do grupo do terminal (fechar o terminal não derruba a API).
        env = ambiente_filho(os.environ, env_extra)
        with log.open("wb") as destino:
            if sys.platform == "win32":
                proc = subprocess.Popen(
                    list(cmd),
                    cwd=cwd,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=destino,
                    stderr=subprocess.STDOUT,
                    creationflags=0x00000008 | 0x00000200,  # DETACHED_PROCESS | NEW_PROCESS_GROUP
                )
            else:
                proc = subprocess.Popen(
                    list(cmd),
                    cwd=cwd,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=destino,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        return proc.pid

    def processo_vivo(self, pid: int) -> bool:
        if pid <= 0:
            return False
        if sys.platform == "win32":
            import ctypes

            # os.kill(pid, 0) no Windows ENCERRA o processo; por isso a consulta é pela API do SO.
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                codigo = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(codigo)):
                    return False
                return codigo.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def linha_de_comando(self, pid: int) -> str | None:
        if pid <= 0:
            return None
        if sys.platform == "win32":
            script = f'(Get-CimInstance Win32_Process -Filter "ProcessId={int(pid)}").CommandLine'
            programa, args = "powershell", ["-NoProfile", "-NonInteractive", "-Command", script]
        else:
            programa, args = "ps", ["-p", str(int(pid)), "-o", "command="]
        exe = self._exe(programa)
        if exe is None:
            return None
        cmd = [exe, *args]
        try:
            r = subprocess.run(
                cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=30, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        texto = r.stdout.decode("utf-8", "replace").strip()
        return texto or None

    def encerrar(self, pid: int) -> None:
        if pid <= 0 or pid == os.getpid():
            raise Falha("PID inválido para encerrar")
        if sys.platform == "win32":
            # /T: a árvore deste PID (o python do venv lança o interpretador real como filho).
            exe = self._exe("taskkill")
            if exe is None:
                raise Falha("programa não encontrado no PATH: 'taskkill'")
            subprocess.run(
                [exe, "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                check=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)

    def porta_ocupada(self, porta: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", porta), timeout=1):
                return True
        except OSError:
            return False

    def api_responde(self, porta: int) -> bool:
        abridor = request.build_opener(request.ProxyHandler({}))
        try:
            abridor.open(f"http://127.0.0.1:{porta}/", timeout=2).close()
        except error.HTTPError:
            return True  # qualquer resposta HTTP prova que a API está de pé
        except (error.URLError, OSError):
            return False
        return True

    def tem_terminal(self) -> bool:
        return sys.stdin is not None and sys.stdin.isatty()

    def pedir(self, pergunta: str) -> str:
        try:
            return input(pergunta)
        except EOFError:
            return ""

    def agora(self) -> datetime:
        return datetime.now(FUSO).replace(tzinfo=None)

    def dormir(self, segundos: float) -> None:
        time.sleep(segundos)

    def abrir_url(self, url: str) -> None:
        webbrowser.open(url)


# --------------------------------------------------------------------------------------
# Operador
# --------------------------------------------------------------------------------------


def pasta_estado_padrao(environ: Mapping[str, str]) -> Path:
    """`%LOCALAPPDATA%\\abako` (no Linux, `~/.local/state/abako`); sempre fora do repositório."""
    base = environ.get("LOCALAPPDATA")
    destino = (
        Path(base) / "abako"
        if base
        else Path(environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "abako"
    )
    try:
        return pasta_fora_do_repo(destino, "pasta de estado")
    except AlvoInvalido as exc:
        raise Falha(str(exc)) from exc


class Operador:
    def __init__(
        self,
        sistema: Sistema,
        raiz: Path,
        pasta_estado: Path,
        porta: int | None = None,
        python: str | None = None,
    ) -> None:
        self.s = sistema
        self.raiz = raiz
        self.estado_dir = pasta_estado
        self._porta = porta  # vem do terminal (ABAKO_PORTA); senão, do processo filho de config
        self.py = python or sys.executable
        self._prd_confirmado = False
        self._config: dict[str, str] | None = None

    # ---- utilidades -----------------------------------------------------------------

    @property
    def porta(self) -> int:
        """Porta da API: ABAKO_PORTA do terminal, senão a da configuração do projeto, senão 8080."""
        if self._porta is None:
            cfg = self.config()
            if cfg.get("porta_invalida"):
                raise Falha(MSG_PORTA_INVALIDA)
            try:
                self._porta = porta_valida(cfg.get("porta"))
            except ValueError as exc:
                raise Falha(MSG_PORTA_INVALIDA) from exc
        return self._porta

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.porta}"

    @property
    def arquivo_pid(self) -> Path:
        return self.estado_dir / "api.pid"

    @property
    def arquivo_log(self) -> Path:
        return self.estado_dir / "api.log"

    def _git(self, *args: str) -> Resultado:
        return self.s.rodar(["git", *args], cwd=self.raiz)

    def _extra(self, alvo: str) -> dict[str, str]:
        """`ABAKO_ENV` do filho; a confirmação do prd só existe depois da digitada."""
        extra = {"ABAKO_ENV": alvo}
        if alvo == "prd":
            if not self._prd_confirmado:
                raise Recusa("acesso ao prd sem confirmação digitada; nada foi executado")
            extra[VAR_CONFIRMA_PRD] = "sim"
        return extra

    def _modulo(self, alvo: str, *args: str, capturar: bool = True) -> Resultado:
        return self.s.rodar(
            [self.py, *args], cwd=self.raiz, env_extra=self._extra(alvo), capturar=capturar
        )

    @staticmethod
    def _codigo_filho(codigo: int) -> int:
        return OK if codigo == 0 else (RECUSADO if codigo == 2 else FALHA)

    def _mostrar(self, resultado: Resultado) -> None:
        texto = saida_segura(resultado.saida)
        if texto:
            print(texto)

    def config(self) -> dict[str, str]:
        """Contêiner, pasta de backups e porta, vindos de um processo filho do projeto."""
        if self._config is None:
            self._config = {}
            try:
                r = self.s.rodar([self.py, "-m", "scripts.config_local"], cwd=self.raiz)
                if r.codigo == 0:
                    dados = json.loads(r.saida.strip().splitlines()[-1])
                    if isinstance(dados, dict):
                        for chave, valor in dados.items():
                            if chave in {"conteiner", "pasta", "porta_invalida"} and isinstance(
                                valor, str
                            ):
                                self._config[chave] = valor
                            elif chave == "porta" and type(valor) is int:
                                self._config[chave] = str(valor)
            except (ValueError, IndexError):
                self._config = {}
        return self._config

    # ---- estado da API (PID e ambiente guardados) -------------------------------------

    def ler_estado(self) -> Estado | None:
        try:
            dados = json.loads(self.arquivo_pid.read_text(encoding="utf-8"))
            pid, env, porta = int(dados["pid"]), str(dados["env"]), int(dados["porta"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if env not in AMBIENTES or pid <= 0:
            return None
        return Estado(pid, env, porta)

    def _gravar_estado(self, estado: Estado) -> None:
        self.estado_dir.mkdir(parents=True, exist_ok=True)
        self.arquivo_pid.write_text(
            json.dumps({"pid": estado.pid, "env": estado.env, "porta": estado.porta}),
            encoding="utf-8",
        )

    def _apagar_estado(self) -> None:
        self.arquivo_pid.unlink(missing_ok=True)

    def _classificar(self, estado: Estado) -> str:
        """`morto`, `abako` (linha lida e é `-m backend`), `outro` (linha lida e não é) ou
        `incerto` (o processo vive mas não consegui ler a linha de comando)."""
        if not self.s.processo_vivo(estado.pid):
            return "morto"
        linha = self.s.linha_de_comando(estado.pid)
        if linha is None:
            return "incerto"
        return "abako" if e_processo_do_abako(linha) else "outro"

    def api_rodando(self) -> Estado | None:
        """O estado guardado, se o PID ainda for um processo do abako; senão `None`."""
        estado = self.ler_estado()
        if estado and self._classificar(estado) == "abako":
            return estado
        return None

    # ---- confirmação ------------------------------------------------------------------

    def exigir_terminal(self) -> None:
        if not self.s.tem_terminal():
            raise Recusa(
                "operação no prd recusada: não há terminal interativo para a confirmação "
                "digitada. Rode você mesmo, num terminal."
            )

    def confirmar(self, o_que: str, palavra: str) -> None:
        """Pede que uma PESSOA digite `palavra`; qualquer outra coisa recusa."""
        self.exigir_terminal()
        print(f"\n*** ATENÇÃO: {o_que} ***")
        resposta = self.s.pedir(f"Para continuar, digite {palavra} (ou Enter para cancelar): ")
        if resposta.strip() != palavra:
            raise Recusa("confirmação não confere; nada foi feito")
        if palavra == PALAVRA_ACESSO:
            self._prd_confirmado = True

    def _confirmar_acesso_prd(self, o_que: str) -> None:
        self.confirmar(f"acesso ao banco REAL (prd): {o_que}", PALAVRA_ACESSO)

    # ---- git --------------------------------------------------------------------------

    def branch_atual(self) -> str:
        r = self._git("branch", "--show-current")
        if r.codigo != 0:
            raise Falha("não consegui ler a branch atual (git)")
        return r.saida.strip()

    def exigir_main(self) -> None:
        branch = self.branch_atual()
        if branch != "main":
            raise Recusa(f"só a partir da main (a branch atual é {branch or 'desconhecida'!r})")

    def exigir_main_no_prd(self, alvo: str) -> None:
        """No prd só a partir da main. No tst (desenvolvimento) só avisa a branch atual: uma
        migração nasce numa branch e é testada no tst antes de ir para a main."""
        if alvo == "prd":
            self.exigir_main()
        else:
            print(
                f"Branch atual: {self.branch_atual() or 'desconhecida'} (no tst a main não é exigida)"
            )

    def exigir_arvore_limpa(self) -> None:
        r = self._git("status", "--porcelain")
        if r.codigo != 0:
            raise Falha("não consegui ler o estado da árvore de trabalho (git)")
        if r.saida.strip():
            raise Recusa(
                "a árvore de trabalho tem alterações não commitadas; "
                "guarde ou descarte antes de atualizar"
            )

    # ---- migrações --------------------------------------------------------------------

    def head_unico(self) -> str:
        r = self.s.rodar([self.py, "-m", "alembic", "heads"], cwd=self.raiz)
        if r.codigo != 0:
            raise Falha("não consegui ler as migrações do repositório (alembic heads)")
        cabecas = revisoes_de(r.saida)
        if len(cabecas) != 1:
            raise Recusa(
                f"o repositório tem {len(cabecas)} cabeças de migração; "
                "resolva (merge) antes de migrar"
            )
        return cabecas[0]

    def versao_atual(self, alvo: str) -> str | None:
        r = self._modulo(alvo, "-m", "alembic", "current")
        if r.codigo != 0:
            raise Falha(f"não consegui ler a versão das migrações do {alvo} (alembic current)")
        atuais = revisoes_de(r.saida)
        if len(atuais) > 1:
            raise Recusa(f"o {alvo} tem mais de uma versão de migração; resolva antes")
        return atuais[0] if atuais else None

    def pendentes(self, atual: str | None, head: str) -> list[tuple[str, str]]:
        r = self.s.rodar(
            [self.py, "-m", "alembic", "history", "-r", f"{atual or 'base'}:{head}"],
            cwd=self.raiz,
        )
        itens = pendentes_de(r.saida) if r.codigo == 0 else []
        if not itens:
            raise Falha("não consegui listar as migrações pendentes (alembic history)")
        return itens

    def pasta_backup(self) -> Path:
        pasta = self.config().get("pasta")
        if not pasta:
            raise Recusa("pasta de backups não configurada (ABAKO_BACKUP_DIR); rode o backup antes")
        return Path(pasta)

    def _nomes_de_backup(self) -> list[str]:
        """Nomes dos arquivos da pasta de backups com tamanho maior que zero (um arquivo vazio
        com nome recente não prova backup). A idade vem só do nome: um arquivo falso com nome
        recente e conteúdo qualquer ainda passa (limitação registrada no ADR 056)."""
        pasta = self.pasta_backup()
        if not pasta.is_dir():
            return []
        return [a.name for a in pasta.iterdir() if a.is_file() and a.stat().st_size > 0]

    def exigir_backup_recente(self, apos_pull: bool = False) -> None:
        achado = ultimo_backup(self._nomes_de_backup(), "prd", self.s.agora())
        comando = "abako backup --alvo prd"
        if achado is None:
            motivo = f"não há backup do prd; rode `{comando}`"
        elif achado[1] > LIMITE_BACKUP:
            motivo = (
                f"o último backup do prd tem {formatar_idade(achado[1])} (o limite é 7 dias); "
                f"rode `{comando}`"
            )
        else:
            return
        if apos_pull:
            raise Recusa(
                f"{motivo}. O código já foi atualizado (git pull feito); "
                "depois do backup rode `abako atualizar` de novo"
            )
        raise Recusa(f"{motivo} e repita")

    def _aplicar_migracoes(self, alvo: str, apos_pull: bool = False) -> None:
        """Com o acesso ao prd já confirmado: compara, lista, exige backup e migra."""
        head = self.head_unico()
        atual = self.versao_atual(alvo)
        if atual == head:
            print(f"Migrações do {alvo}: já na versão do repositório ({head}).")
            return
        itens = self.pendentes(atual, head)
        print(f"Migrações pendentes no {alvo} (de {atual or 'vazio'} até {head}):")
        for rev, desc in itens:
            print(f"  {rev}: {desc}")
        if alvo == "prd":
            self.exigir_backup_recente(apos_pull)
            self.confirmar(
                f"aplicar {len(itens)} migração(ões) no banco REAL (prd)", PALAVRA_MIGRAR
            )
        r = self._modulo(alvo, "-m", "alembic", "upgrade", head)
        self._mostrar(r)
        if r.codigo != 0:
            raise Falha(f"a migração do {alvo} falhou (código {r.codigo})")
        print(f"Migrações do {alvo}: aplicadas até {head}.")

    # ---- subcomandos ------------------------------------------------------------------

    def ajuda(self) -> int:
        print(AJUDA)
        return OK

    def raiz_cmd(self) -> int:
        """Pasta de trabalho do processo: o invólucro entra na raiz com a letra do drive em
        maiúsculo; este diagnóstico permite conferir isso."""
        print(os.getcwd())
        return OK

    def status(self, com_prd: bool = False) -> int:
        print("== abako: situação ==")
        self._linha("Banco (contêiner)", self._st_conteiner)
        self._linha("API", self._st_api)
        self._linha("Migrações tst", lambda: self._st_versao("tst"))
        if com_prd:
            self._linha("Migrações prd", lambda: self._st_versao("prd", pedir_confirmacao=True))
        else:
            print("Migrações prd: não consultadas (rode `abako status --prd`; pede confirmação)")
        self._linha("Último backup do prd", self._st_backup)
        self._linha("Build do front", self._st_build)
        self._linha("Git", self._st_git)
        return OK

    @staticmethod
    def _linha(rotulo: str, funcao: Callable[[], str]) -> None:
        try:
            texto = funcao()
        except (Falha, Recusa) as exc:
            texto = f"indisponível ({exc})"
        except Exception as exc:  # noqa: BLE001  # só a classe: a mensagem pode ter URL
            texto = f"indisponível ({descrever_excecao(exc)})"
        print(f"{rotulo}: {texto}")

    def _st_conteiner(self) -> str:
        nome = self.config().get("conteiner")
        if not nome:
            return "indisponível (COMPOSE_PROJECT_NAME não definido)"
        fmt = "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}"
        r = self.s.rodar(["docker", "inspect", "-f", fmt, nome])
        if r.codigo != 0:
            return "não encontrado ou Docker fechado (rode `abako subir`)"
        situacao, _, saude = r.saida.strip().partition("|")
        if situacao == "running" and saude == "healthy":
            return "de pé e saudável"
        return f"{situacao or 'desconhecido'}, saúde: {saude or 'sem verificação'}"

    def _st_api(self) -> str:
        estado = self.api_rodando()
        if estado:
            return f"rodando em {self.url} (PID {estado.pid}), {aviso_ambiente(estado.env)}"
        if self.s.porta_ocupada(self.porta):
            return f"porta {self.porta} ocupada por OUTRO programa (não é a API do abako)"
        return f"parada (porta {self.porta} livre)"

    def _st_versao(self, alvo: str, pedir_confirmacao: bool = False) -> str:
        if pedir_confirmacao:
            self._confirmar_acesso_prd("só leitura da versão das migrações")
        head = self.head_unico()
        atual = self.versao_atual(alvo)
        if atual == head:
            return f"{atual} (em dia com o repositório)"
        return f"{atual or 'vazio'} (o repositório está em {head}: PENDENTE)"

    def _st_backup(self) -> str:
        achado = ultimo_backup(self._nomes_de_backup(), "prd", self.s.agora())
        if achado is None:
            return "nenhum encontrado"
        nome, idade = achado
        aviso = "" if idade <= LIMITE_BACKUP else " [ANTIGO: mais de 7 dias]"
        return f"há {formatar_idade(idade)} ({nome}){aviso}"

    def _st_build(self) -> str:
        motivo = build_desatualizado(self.raiz / "frontend")
        return "em dia" if motivo is None else f"DESATUALIZADO ({motivo})"

    def _st_git(self) -> str:
        branch = self.branch_atual()
        r = self._git("rev-list", "--count", "HEAD..origin/main")
        atras = r.saida.strip() if r.codigo == 0 and r.saida.strip().isdigit() else "?"
        return f"branch {branch or 'desconhecida'}, {atras} commit(s) atrás de origin/main"

    def _esperar_banco(self) -> None:
        nome = self.config().get("conteiner")
        if not nome:
            raise Falha("COMPOSE_PROJECT_NAME não definido: não sei qual é o contêiner do banco")
        fmt = "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}"
        decorrido = 0.0
        while decorrido <= ESPERA_BANCO_S:
            r = self.s.rodar(["docker", "inspect", "-f", fmt, nome])
            if r.codigo == 0 and r.saida.strip() == "running|healthy":
                return
            self.s.dormir(2)
            decorrido += 2
        raise Falha(f"o banco não ficou saudável em {ESPERA_BANCO_S} s (veja o Docker Desktop)")

    def build(self) -> int:
        frontend = self.raiz / "frontend"
        if not (frontend / "node_modules").is_dir():
            print("Instalando dependências do front (npm ci)...")
            r = self.s.rodar(["npm", "ci"], cwd=frontend, capturar=False)
            if r.codigo != 0:
                raise Falha(f"npm ci falhou (código {r.codigo})")
        print("Construindo o front (npm run build)...")
        r = self.s.rodar(["npm", "run", "build"], cwd=frontend, capturar=False)
        if r.codigo != 0:
            raise Falha(f"o build do front falhou (código {r.codigo})")
        print("Build concluído.")
        return OK

    def subir(self, ambiente: str = "prd") -> int:
        if ambiente not in AMBIENTES:
            raise Recusa(f"ambiente inválido: {ambiente!r}")
        estado = self.ler_estado()
        if estado is not None:
            situacao = self._classificar(estado)
            if situacao == "incerto":
                raise Recusa(MSG_NAO_CONFERI)
            if situacao == "abako":
                if estado.env != ambiente:
                    raise Recusa(
                        f"a API já roda em {estado.env}; use `abako reiniciar` ou `abako parar`"
                    )
                print("A API já está rodando.")
                self._anunciar(estado.env)
                return OK
            self._apagar_estado()  # PID velho (morto ou reaproveitado por outro programa)
        if self.s.porta_ocupada(self.porta):
            raise Recusa(
                f"a porta {self.porta} já está ocupada por outro programa; nada foi iniciado "
                "(veja docs/operacao/subir-e-atualizar.md)"
            )
        print(aviso_ambiente(ambiente))
        print("Subindo o banco (docker compose up -d)...")
        r = self.s.rodar(["docker", "compose", "up", "-d"], cwd=self.raiz)
        if r.codigo != 0:
            self._mostrar(r)
            raise Falha("docker compose falhou (o Docker Desktop está aberto?)")
        self._esperar_banco()
        print("Banco saudável.")
        motivo = build_desatualizado(self.raiz / "frontend")
        if motivo:
            print(f"Build do front desatualizado ({motivo}); refazendo.")
            self.build()
        self.estado_dir.mkdir(parents=True, exist_ok=True)
        pid = self.s.iniciar_em_segundo_plano(
            [self.py, "-m", "backend"],
            cwd=self.raiz,
            env_extra={"ABAKO_ENV": ambiente},
            log=self.arquivo_log,
        )
        self._gravar_estado(Estado(pid, ambiente, self.porta))
        self._esperar_api(pid)
        self._anunciar(ambiente)
        return OK

    def _esperar_api(self, pid: int) -> None:
        decorrido = 0.0
        while decorrido <= ESPERA_API_S:
            if not self.s.processo_vivo(pid):
                self._apagar_estado()
                raise Falha(f"a API encerrou ao iniciar. Fim do log:\n{self._cauda_log()}")
            if self.s.api_responde(self.porta):
                return
            self.s.dormir(1)
            decorrido += 1
        self.s.encerrar(pid)
        self._apagar_estado()
        raise Falha(
            f"a API não respondeu em {ESPERA_API_S} s e foi encerrada. Fim do log:\n"
            f"{self._cauda_log()}"
        )

    def _cauda_log(self) -> str:
        try:
            texto = self.arquivo_log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "(sem log)"
        return saida_segura(texto, max_linhas=10) or "(log vazio)"

    def _anunciar(self, ambiente: str) -> None:
        print(f"\n{aviso_ambiente(ambiente)}")
        print(f"App: {self.url}")
        print(f"Log da API: {self.arquivo_log}")

    def parar(self) -> int:
        estado = self.ler_estado()
        if estado is None:
            print("A API não está rodando (nenhum PID guardado). O banco não foi tocado.")
            return OK
        situacao = self._classificar(estado)
        if situacao == "morto":
            self._apagar_estado()
            print("A API já não estava rodando; o arquivo de PID velho foi removido.")
            return OK
        if situacao == "incerto":
            # Não li a linha de comando (PowerShell falhou ou demorou): não sei de quem é o PID.
            raise Recusa(MSG_NAO_CONFERI)
        if situacao == "outro":
            self._apagar_estado()
            raise Recusa(
                f"o PID guardado ({estado.pid}) agora pertence a outro programa; "
                "nenhum processo foi encerrado (o arquivo de PID velho foi removido)"
            )
        self.s.encerrar(estado.pid)
        for _ in range(ESPERA_ENCERRAR_S):
            if not self.s.processo_vivo(estado.pid):
                break
            self.s.dormir(1)
        else:
            raise Falha(f"o processo {estado.pid} não encerrou em {ESPERA_ENCERRAR_S} s")
        self._apagar_estado()
        print("API encerrada. O banco continua de pé.")
        return OK

    def reiniciar(self) -> int:
        estado = self.api_rodando()
        ambiente = estado.env if estado else "prd"
        if estado is None:
            print("A API não estava rodando; subindo no ambiente padrão (prd).")
        self.parar()
        return self.subir(ambiente)

    def atualizar(self) -> int:
        self.exigir_terminal()  # recusa cedo: o fluxo acessa o prd
        self.exigir_arvore_limpa()
        self.exigir_main_no_prd("prd")
        rodando = self.api_rodando()
        if self._git("fetch").codigo != 0:
            raise Falha("git fetch falhou (sem rede?)")
        self._confirmar_acesso_prd(
            "atualizar o código, ler a versão das migrações e, se houver pendentes, migrar"
        )
        if self._git("pull", "--ff-only").codigo != 0:
            raise Falha("git pull --ff-only falhou (a main local divergiu da remota)")
        self._aplicar_migracoes("prd", apos_pull=True)
        motivo = build_desatualizado(self.raiz / "frontend")
        if motivo:
            self.build()
        else:
            print("Build do front em dia.")
        if rodando:
            print("Reiniciando a API...")
            self.parar()
            return self.subir(rodando.env)
        print("A API não estava rodando; use `abako subir` quando quiser.")
        return OK

    def backup(self, alvo: str = "tst") -> int:
        if alvo == "prd":
            self.exigir_terminal()
            self._confirmar_acesso_prd("gerar backup cifrado do banco real")
        r = self._modulo(alvo, "-m", "scripts.backup", "--alvo", alvo)
        self._mostrar(r)
        return self._codigo_filho(r.codigo)

    def migrar(self, alvo: str = "tst") -> int:
        if alvo == "prd":
            self.exigir_terminal()
        self.exigir_main_no_prd(alvo)
        if alvo == "prd":
            self._confirmar_acesso_prd("ler a versão das migrações e, se houver pendentes, migrar")
        self._aplicar_migracoes(alvo)
        return OK

    def pipeline(self, alvo: str = "tst") -> int:
        if alvo == "prd":
            self.exigir_terminal()
            self._confirmar_acesso_prd("rodar o pipeline analítico lendo o banco real")
        r = self._modulo(alvo, "-m", "pipeline", "--alvo", alvo)
        self._mostrar(r)
        return self._codigo_filho(r.codigo)

    def check(self) -> int:
        print("Rodando `check --com-banco`: leva uns 10 minutos (a etapa de banco é a mais lenta).")
        r = self.s.rodar(
            [self.py, "-m", "scripts.check", "--com-banco"], cwd=self.raiz, capturar=False
        )
        return OK if r.codigo == 0 else FALHA

    def abrir(self) -> int:
        if self.api_rodando() is None:
            if self.s.porta_ocupada(self.porta):
                raise Recusa(
                    f"a porta {self.porta} está ocupada por outro programa, não pela API do "
                    "abako; não abro o navegador (rode `abako status`)"
                )
            raise Falha("a API não está rodando; rode `abako subir` primeiro")
        self.s.abrir_url(self.url)
        print(f"Abrindo {self.url} no navegador.")
        return OK


AJUDA = """abako: operação local (uso: abako <subcomando> [opções])

  ajuda                 esta lista
  status [--prd]        situação: banco, API, migrações, backup, build, git
                        (--prd também lê a versão das migrações do prd; pede confirmação)
  subir [--tst]         sobe o banco, refaz o build se preciso e inicia a API (padrão: prd)
  parar                 encerra só a API iniciada por este comando (o banco continua)
  reiniciar             parar + subir no mesmo ambiente
  build                 refaz o front (npm ci se faltar node_modules, depois npm run build)
  atualizar             git pull --ff-only (só na main, árvore limpa) + migrações pendentes
                        do prd + build + reinicia a API
  backup  [--alvo prd|tst]   backup cifrado (padrão: tst)
  migrar  [--alvo prd|tst]   aplica migrações pendentes (padrão: tst; no prd só na main)
  pipeline [--alvo prd|tst]  atualiza o analítico DuckDB (padrão: tst)
  check                 lint, tipos e todos os testes (leva uns 10 minutos)
  abrir                 abre o app no navegador
  raiz                  mostra a pasta de trabalho atual (diagnóstico do invólucro)

No prd, backup, migrar, pipeline, atualizar e `status --prd` pedem que VOCÊ digite a
confirmação num terminal; sem terminal interativo, recusam.
Códigos de saída: 0 ok, 1 falha, 2 recusado por regra de segurança.
Exemplos:
  abako subir          abako subir --tst        abako backup --alvo prd
  abako status         abako atualizar          abako parar
Passo a passo: docs/operacao/subir-e-atualizar.md"""


def traduzir_erro_argparse(mensagem: str) -> str:
    """Mensagem do argparse (em inglês) em português; repete só o valor digitado."""
    m = re.search(r"invalid choice: (.*?) \(choose from", mensagem, re.DOTALL)
    if m and "--alvo" in mensagem:
        return f"valor inválido para --alvo: {m.group(1)} (use tst ou prd)"
    if m:
        return f"subcomando desconhecido: {m.group(1)}"
    m = re.search(r"unrecognized arguments: (.*)", mensagem, re.DOTALL)
    if m:
        return f"argumentos não reconhecidos: {m.group(1)}"
    return "uso inválido"


class ParserPt(argparse.ArgumentParser):
    """ArgumentParser com erro em português e código de saída 2."""

    def error(self, message: str) -> NoReturn:
        print(
            f"abako: {traduzir_erro_argparse(message)}. Rode `abako ajuda` para ver os subcomandos.",
            file=sys.stderr,
        )
        raise SystemExit(RECUSADO)


def montar_parser() -> argparse.ArgumentParser:
    p = ParserPt(prog="abako", add_help=False, description="Operação local")
    sub = p.add_subparsers(dest="comando")
    sub.add_parser("ajuda")
    st = sub.add_parser("status")
    st.add_argument("--prd", action="store_true")
    su = sub.add_parser("subir")
    su.add_argument("--tst", action="store_true")
    for nome in ("parar", "reiniciar", "build", "atualizar", "check", "abrir", "raiz"):
        sub.add_parser(nome)
    for nome in ("backup", "migrar", "pipeline"):
        sp = sub.add_parser(nome)
        sp.add_argument("--alvo", choices=list(AMBIENTES), default="tst")
    return p


def main(
    argv: Sequence[str] | None = None,
    *,
    sistema: Sistema | None = None,
    raiz: Path | None = None,
    pasta_estado: Path | None = None,
    python: str | None = None,
) -> int:
    if argv is not None and list(argv) in (["-h"], ["--help"]):
        print(AJUDA)
        return OK
    try:
        a = montar_parser().parse_args(argv)
    except SystemExit as exc:  # erro de uso (código 2)
        return int(exc.code) if isinstance(exc.code, int) else RECUSADO
    if a.comando is None or a.comando == "ajuda":
        print(AJUDA)
        return OK
    try:
        operador = Operador(
            sistema or SistemaReal(),
            raiz or Path(normalizar_drive(str(RAIZ))),
            pasta_estado or pasta_estado_padrao(os.environ),
            porta=_porta_do_terminal(os.environ),
            python=python,
        )
        return _despachar(operador, a)
    except Recusa as exc:
        print(f"RECUSADO: {exc}", file=sys.stderr)
        return RECUSADO
    except Falha as exc:
        print(f"FALHOU: {exc}", file=sys.stderr)
        return FALHA
    except KeyboardInterrupt:
        print("Interrompido.", file=sys.stderr)
        return FALHA
    except Exception as exc:  # noqa: BLE001  # só a classe: a mensagem pode ter URL ou valor
        print(f"FALHOU: erro inesperado ({descrever_excecao(exc)})", file=sys.stderr)
        return FALHA


def _porta_do_terminal(environ: Mapping[str, str]) -> int | None:
    """ABAKO_PORTA do terminal, se houver (sobrescreve a da configuração); vazia = não definida."""
    valor = environ.get(VAR_PORTA, "").strip()
    if not valor:
        return None
    try:
        return porta_valida(valor)
    except ValueError as exc:
        raise Falha(MSG_PORTA_INVALIDA) from exc


def _despachar(op: Operador, a: argparse.Namespace) -> int:
    if a.comando == "status":
        return op.status(com_prd=a.prd)
    if a.comando == "subir":
        return op.subir("tst" if a.tst else "prd")
    if a.comando in {"backup", "migrar", "pipeline"}:
        return int(getattr(op, a.comando)(a.alvo))
    if a.comando == "raiz":
        return op.raiz_cmd()
    return int(getattr(op, a.comando)())


if __name__ == "__main__":
    for fluxo in (sys.stdout, sys.stderr):
        if isinstance(fluxo, io.TextIOWrapper):
            fluxo.reconfigure(encoding="utf-8")
    raise SystemExit(main())
