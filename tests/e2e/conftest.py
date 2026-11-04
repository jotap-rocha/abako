"""Jornadas e2e: servidor de verdade contra o `tst` + navegador de verdade (Playwright).

O front é construído numa pasta temporária (nunca em `frontend/dist`, que o servidor do `prd`
serve). O navegador é o Edge instalado (canal `msedge`) no Windows e o Chromium do Playwright no
CI; `ABAKO_E2E_NAVEGADOR` escolhe (`msedge`, `chrome` ou `chromium`).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from tests.backend.conftest import Usuario, apagar_usuarios, criar_usuario
from tests.db.conftest import esquema, url_app, url_tst  # noqa: F401  (fixtures reutilizadas)

RAIZ = Path(__file__).resolve().parents[2]
NAVEGADORES = ("msedge", "chrome", "chromium")


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta: int = s.getsockname()[1]
        return porta


def _esperar_no_ar(base: str, processo: subprocess.Popen[bytes], limite_s: float = 30) -> None:
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        if processo.poll() is not None:
            pytest.fail(f"o servidor de teste saiu com código {processo.returncode}")
        try:
            urllib.request.urlopen(f"{base}/api/auth/eu", timeout=1)  # noqa: S310  (loopback)
            return
        except urllib.error.HTTPError:
            return  # 401 = no ar
        except OSError:
            time.sleep(0.3)
    pytest.fail("o servidor de teste não respondeu a tempo")


@pytest.fixture(scope="session")
def dist_e2e(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build do front numa pasta temporária, para não tocar o `frontend/dist`."""
    npm = shutil.which("npm")
    if npm is None:
        pytest.fail("npm não encontrado no PATH (o e2e precisa construir o front)")
    destino = tmp_path_factory.mktemp("dist")
    subprocess.run(
        [npm, "exec", "--", "vite", "build", "--outDir", str(destino), "--emptyOutDir"],
        cwd=RAIZ / "frontend",
        check=True,
        stdout=subprocess.DEVNULL,
    )
    assert (destino / "index.html").is_file()
    return destino


@pytest.fixture
def servidor(url_app: str, dist_e2e: Path, tmp_path: Path) -> Iterator[str]:  # noqa: F811
    """`python -m backend` no `tst`, numa porta livre de 127.0.0.1. Devolve a URL base."""
    porta = _porta_livre()
    # Nada de `ABAKO_*` herdado (URL do dono, senhas dos papéis, hosts/origens do `.env`): o
    # servidor recebe só o que precisa. Do resto do ambiente vem o básico do sistema operacional.
    env = {
        **{k: v for k, v in os.environ.items() if not k.upper().startswith("ABAKO_")},
        "ABAKO_ENV": "tst",
        "ABAKO_DB_APP_URL": url_app,
        "ABAKO_PORTA": str(porta),
        "ABAKO_FRONTEND_DIST": str(dist_e2e),
        "PYTHONPATH": str(RAIZ),
    }
    log = (tmp_path / "servidor.log").open("wb")
    # Roda fora da raiz: o pydantic-settings lê o arquivo de ambiente da pasta atual, e o
    # servidor do e2e não deve herdar nada dele.
    processo = subprocess.Popen(
        [sys.executable, "-m", "backend"], cwd=tmp_path, env=env, stdout=log, stderr=log
    )
    base = f"http://127.0.0.1:{porta}"
    try:
        try:
            _esperar_no_ar(base, processo)
        except BaseException:
            # Diagnóstico no CI: o log do uvicorn (só tst e dado sintético) vai para a saída.
            log.flush()
            print((tmp_path / "servidor.log").read_text(encoding="utf-8", errors="replace"))
            raise
        yield base
    finally:
        processo.terminate()
        try:
            processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            processo.kill()
        log.close()


@pytest.fixture
def usuario_e2e(esquema: str) -> Iterator[Usuario]:  # noqa: F811
    u = criar_usuario(esquema, "e2e")
    yield u
    apagar_usuarios(esquema, [u])


@contextmanager
def _loop_que_abre_subprocesso() -> Iterator[None]:
    """O backend fixa o loop Selector no Windows (psycopg); o Playwright precisa do Proactor
    para abrir o processo dele. Envolve só o `start()`; a política anterior volta logo depois."""
    if sys.platform != "win32":
        yield
        return
    anterior = asyncio.get_event_loop_policy()
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        yield
    finally:
        asyncio.set_event_loop_policy(anterior)


@pytest.fixture(scope="session")
def navegador() -> Iterator[Browser]:
    padrao = "msedge" if sys.platform == "win32" else "chromium"
    escolhido = os.environ.get("ABAKO_E2E_NAVEGADOR", padrao)
    if escolhido not in NAVEGADORES:
        pytest.fail(f"ABAKO_E2E_NAVEGADOR deve ser um de {NAVEGADORES}, não {escolhido!r}")
    with _loop_que_abre_subprocesso():
        p = sync_playwright().start()
    try:
        canal = None if escolhido == "chromium" else escolhido
        b = p.chromium.launch(channel=canal, headless=True)
        yield b
        b.close()
    finally:
        p.stop()


@pytest.fixture
def pagina(navegador: Browser) -> Iterator[Page]:
    contexto = navegador.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo")
    contexto.set_default_timeout(10_000)
    p = contexto.new_page()
    yield p
    contexto.close()
