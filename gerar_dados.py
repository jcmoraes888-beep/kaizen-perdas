"""
Fase 1 - Gera a base de dados fictícia do App Kaizen de Perdas.

Cria o arquivo kaizen.db (SQLite) com 5 tabelas:
  maquinas, motivos, materiais, producao (kg utilizado por dia) e perdas.

Todos os dados são FICTÍCIOS: uma fábrica de embalagens com 10 máquinas
e 90 dias de operação. Rode de novo a qualquer momento para recriar a base.

Uso:  python gerar_dados.py
"""

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "kaizen.db"
DIAS = 90
SEMENTE = 42  # mesma semente = mesmos dados sempre

MAQUINAS = [f"AUTO {i}" for i in range(1, 11)]
META_PERDA_PCT = 4.0

# (descricao, tipo_acao)
MOTIVOS = [
    ("Regulagem", "Operacional"),
    ("Setup / troca de molde", "Operacional"),
    ("Material fora de especificação", "Material"),
    ("Máquina fora do ponto", "Mecânica"),
    ("Falha de selagem", "Mecânica"),
    ("Outros", "Operacional"),
]

# (nome, custo por kg em R$) - valores fictícios
MATERIAIS = [("Lâmina PET", 14.50), ("Bobina", 22.00)]

TURNOS = ["1º turno", "2º turno"]
OPERADORES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabi", "Hugo"]

# Perfil de cada máquina: kg utilizado/dia e % de perda "típica".
# AUTO 8 é a máquina problemática (como no caso real que inspirou o app).
PERFIL = {
    "AUTO 1": (90, 5.0), "AUTO 2": (80, 6.5), "AUTO 3": (85, 7.5),
    "AUTO 4": (150, 5.5), "AUTO 5": (160, 4.2), "AUTO 6": (155, 3.2),
    "AUTO 7": (110, 6.0), "AUTO 8": (75, 9.0), "AUTO 9": (95, 4.5),
    "AUTO 10": (85, 7.0),
}

# Peso de cada motivo por máquina (padrão = distribuição geral).
PESO_PADRAO = [30, 15, 15, 20, 15, 5]
PESO_ESPECIAL = {
    "AUTO 8": [45, 5, 5, 35, 8, 2],   # regulagem + máquina fora do ponto
    "AUTO 3": [15, 10, 45, 15, 10, 5],  # problema de material
}


def criar_tabelas(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        DROP TABLE IF EXISTS perdas;
        DROP TABLE IF EXISTS producao;
        DROP TABLE IF EXISTS maquinas;
        DROP TABLE IF EXISTS motivos;
        DROP TABLE IF EXISTS materiais;

        CREATE TABLE maquinas (
            maquina_id     INTEGER PRIMARY KEY,
            nome           TEXT NOT NULL UNIQUE,
            setor          TEXT NOT NULL,
            meta_perda_pct REAL NOT NULL,
            ativa          INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE motivos (
            motivo_id  INTEGER PRIMARY KEY,
            descricao  TEXT NOT NULL UNIQUE,
            tipo_acao  TEXT NOT NULL  -- Operacional / Mecânica / Material
        );

        CREATE TABLE materiais (
            material_id INTEGER PRIMARY KEY,
            nome        TEXT NOT NULL UNIQUE,
            custo_kg_rs REAL NOT NULL
        );

        CREATE TABLE producao (
            data         TEXT NOT NULL,
            maquina_id   INTEGER NOT NULL REFERENCES maquinas(maquina_id),
            kg_utilizado REAL NOT NULL,
            PRIMARY KEY (data, maquina_id)
        );

        CREATE TABLE perdas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            data        TEXT NOT NULL,
            turno       TEXT NOT NULL,
            maquina_id  INTEGER NOT NULL REFERENCES maquinas(maquina_id),
            operador    TEXT NOT NULL,
            material_id INTEGER NOT NULL REFERENCES materiais(material_id),
            kg          REAL NOT NULL CHECK (kg > 0),
            motivo_id   INTEGER NOT NULL REFERENCES motivos(motivo_id),
            observacao  TEXT
        );
        """
    )


def popular(con: sqlite3.Connection) -> None:
    rnd = random.Random(SEMENTE)

    con.executemany(
        "INSERT INTO maquinas (nome, setor, meta_perda_pct) VALUES (?, ?, ?)",
        [(m, "Termoformagem", META_PERDA_PCT) for m in MAQUINAS],
    )
    con.executemany("INSERT INTO motivos (descricao, tipo_acao) VALUES (?, ?)", MOTIVOS)
    con.executemany("INSERT INTO materiais (nome, custo_kg_rs) VALUES (?, ?)", MATERIAIS)

    maq_id = {nome: i for i, nome in enumerate(MAQUINAS, start=1)}
    inicio = date.today() - timedelta(days=DIAS)

    producao, perdas = [], []
    for d in range(DIAS):
        dia = inicio + timedelta(days=d)
        if dia.weekday() == 6:  # domingo parado
            continue
        for nome in MAQUINAS:
            base_kg, perda_pct = PERFIL[nome]
            kg_util = round(base_kg * rnd.uniform(0.85, 1.15), 1)
            producao.append((dia.isoformat(), maq_id[nome], kg_util))

            # perda total do dia, com variação
            perda_dia = kg_util * perda_pct / 100 * rnd.uniform(0.6, 1.4)
            # divide em 1 a 4 apontamentos
            n = rnd.randint(1, 4)
            partes = [rnd.random() for _ in range(n)]
            soma = sum(partes)
            pesos = PESO_ESPECIAL.get(nome, PESO_PADRAO)
            for p in partes:
                kg = round(perda_dia * p / soma, 2)
                if kg < 0.05:
                    continue
                motivo = rnd.choices(range(1, len(MOTIVOS) + 1), weights=pesos)[0]
                material = rnd.choices([1, 2], weights=[75, 25])[0]
                perdas.append((
                    dia.isoformat(), rnd.choice(TURNOS), maq_id[nome],
                    rnd.choice(OPERADORES), material, kg, motivo, None,
                ))

    con.executemany(
        "INSERT INTO producao (data, maquina_id, kg_utilizado) VALUES (?, ?, ?)", producao
    )
    con.executemany(
        """INSERT INTO perdas (data, turno, maquina_id, operador, material_id,
                               kg, motivo_id, observacao)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        perdas,
    )


def main() -> None:
    with sqlite3.connect(DB_PATH) as con:
        criar_tabelas(con)
        popular(con)
        n_perdas = con.execute("SELECT COUNT(*) FROM perdas").fetchone()[0]
        kg = con.execute("SELECT ROUND(SUM(kg), 1) FROM perdas").fetchone()[0]
    print(f"Base criada em {DB_PATH.name}: {n_perdas} apontamentos, {kg} kg de perda.")


if __name__ == "__main__":
    main()