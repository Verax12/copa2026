"""Placar previsto COERENTE com o resultado favorito.

Antes, o painel mostrava a *moda* da matriz de placares M (argmax global). Em
jogos parelhos/de poucos gols, essa moda às vezes cai num empate (1-1, 0-0)
mesmo quando o resultado mais provável (V/E/D) é uma vitória — gerando a
contradição "previsto 1-1" e ao mesmo tempo "favorito: Brasil vence".

Aqui o placar é escolhido em DOIS passos, como o usuário espera:
  1) decide o RESULTADO favorito = argmax([ph, pd, pa]);
  2) escolhe o PLACAR mais provável DENTRO desse resultado.

ph/pd/pa e a matriz M vêm da MESMA fonte (a matriz, calibrada quando aplicável),
então favorito e placar nunca se contradizem.

Convenção de resultado: 0 = vitória do mandante, 1 = empate, 2 = vitória do
visitante (mesma de track._outcome e da ordem [ph, pd, pa]).
"""
from __future__ import annotations

import numpy as np


def outcome_probs_from_matrix(M) -> tuple[float, float, float]:
    """(ph, pd, pa) a partir da matriz de placares: triângulo inferior = mandante
    vence, diagonal = empate, triângulo superior = visitante vence."""
    M = np.asarray(M, dtype=float)
    ph = float(np.tril(M, -1).sum())
    pd = float(np.trace(M))
    pa = float(np.triu(M, 1).sum())
    return ph, pd, pa


def favored_scoreline(M, probs: tuple[float, float, float] | None = None):
    """Retorna (favored, (gi, gj), (ph, pd, pa)).

    favored : 0|1|2 = resultado mais provável (argmax de [ph, pd, pa]).
    (gi, gj): placar mais provável DENTRO do resultado favorito.

    `probs` pode ser passado quando já se tem as probabilidades oficiais do
    modelo (ex.: model.outcome_probs); nesse caso o favorito é decidido por elas
    e só o placar é buscado na matriz — evitando qualquer divergência numérica.
    """
    M = np.asarray(M, dtype=float)
    if probs is None:
        probs = outcome_probs_from_matrix(M)
    ph, pd, pa = (float(probs[0]), float(probs[1]), float(probs[2]))
    favored = int(np.argmax([ph, pd, pa]))

    rows, cols = np.indices(M.shape)
    if favored == 0:        # vitória do mandante: linha > coluna
        region = rows > cols
    elif favored == 1:      # empate: diagonal
        region = rows == cols
    else:                   # vitória do visitante: coluna > linha
        region = rows < cols

    masked = np.where(region, M, -np.inf)
    if not np.isfinite(masked).any():        # região vazia (matriz degenerada)
        gi, gj = np.unravel_index(int(M.argmax()), M.shape)
    else:
        gi, gj = np.unravel_index(int(np.argmax(masked)), M.shape)
    return favored, (int(gi), int(gj)), (ph, pd, pa)
