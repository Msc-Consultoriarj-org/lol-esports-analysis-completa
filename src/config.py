"""
Configurações globais do projeto.
"""

from pathlib import Path
import os

# =============================================================================
# PATHS
# =============================================================================

# Detecta o diretório raiz do projeto
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# Diretórios de dados
DATA_DIR = PROJECT_ROOT / "Data"
PARQUET_DIR = DATA_DIR / "parquet"
CSV_DIR = DATA_DIR / "CSV" / "Todas as Partidas"
JSON_DIR = DATA_DIR / "JSON"
MARKDOWN_DIR = DATA_DIR / "Markdown"
META_DIR = DATA_DIR / "Meta"
LIGAS_DIR = DATA_DIR / "Ligas"

# Diretórios de saída
MODELS_DIR = PROJECT_ROOT / "models"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"

# =============================================================================
# HUGGINGFACE CONFIG
# =============================================================================

HF_DATASET_REPO = "moisesmsconsultoria/lol-esports-data"
HF_MODEL_REPO = "moisesmsconsultoria/lol-esports-predictor"

# =============================================================================
# DATA CONFIG
# =============================================================================

# Anos disponíveis
YEARS = list(range(2014, 2027))  # 2014-2026

# Arquivo consolidado
ALL_YEARS_FILE = "lol_esports_ALL_YEARS.parquet"

# Colunas importantes para o modelo
TARGET_COLUMN = "result"  # 1 = vitória, 0 = derrota

# Colunas de identificação
ID_COLUMNS = [
    "gameid", "league", "year", "split", "playoffs",
    "date", "game", "patch", "side", "position",
    "playername", "playerid", "teamname", "teamid", "champion"
]

# Colunas de draft
DRAFT_COLUMNS = [
    "ban1", "ban2", "ban3", "ban4", "ban5",
    "pick1", "pick2", "pick3", "pick4", "pick5"
]

# Colunas de objetivos
OBJECTIVE_COLUMNS = [
    "firstblood", "firstdragon", "firstherald", "firstbaron", "firsttower",
    "dragons", "barons", "towers", "inhibitors", "heralds", 
    "opp_dragons", "opp_barons", "opp_towers", "opp_inhibitors"
]

# Colunas de economia @15min (mais preditivas)
ECONOMY_15_COLUMNS = [
    "goldat15", "xpat15", "csat15",
    "golddiffat15", "xpdiffat15", "csdiffat15"
]

# Colunas de economia @10min
ECONOMY_10_COLUMNS = [
    "goldat10", "xpat10", "csat10",
    "golddiffat10", "xpdiffat10", "csdiffat10"
]

# Colunas de combate
COMBAT_COLUMNS = [
    "kills", "deaths", "assists", "teamkills", "teamdeaths",
    "damagetochampions", "dpm", "damageshare"
]

# Colunas de visão
VISION_COLUMNS = [
    "wardsplaced", "wardskilled", "controlwardsbought", "visionscore"
]

# =============================================================================
# MODEL CONFIG
# =============================================================================

# Features para treino (draft-based - disponíveis antes da partida)
DRAFT_FEATURES = [
    "side",  # Blue/Red
    "champion",  # Champion selecionado
    "ban1", "ban2", "ban3", "ban4", "ban5",
    "pick1", "pick2", "pick3", "pick4", "pick5",
    "league",  # Liga (LCK, LPL, LEC, etc.)
    "patch",  # Versão do jogo
]

# Features derivadas (calculadas)
DERIVED_FEATURES = [
    "team_historical_winrate",
    "champion_winrate_patch",
    "champion_winrate_league",
    "matchup_winrate",  # vs composição adversária
    "side_winrate_league",
    "blue_side_advantage",
]

# Configuração de Rolling Window
ROLLING_WINDOW_CONFIG = {
    "train_weeks": 8,  # Semanas de treino
    "test_weeks": 1,   # Semana de teste
    "min_matches": 50,  # Mínimo de partidas para treinar
}

# =============================================================================
# LIGAS PRINCIPAIS
# =============================================================================

TIER1_LEAGUES = ["LCK", "LPL", "LEC", "LCS"]
TIER2_LEAGUES = ["CBLOL", "LLA", "PCS", "VCS", "LJL"]
INTERNATIONAL = ["MSI", "Worlds", "WLDs"]

# Mapeamento de ligas
LEAGUE_TIERS = {
    **{league: 1 for league in TIER1_LEAGUES},
    **{league: 2 for league in TIER2_LEAGUES},
    **{league: 0 for league in INTERNATIONAL},  # 0 = Internacional
}

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def get_parquet_path(year: int | str = "ALL_YEARS") -> Path:
    """Retorna o caminho do arquivo parquet para um ano específico."""
    if year == "ALL_YEARS":
        return PARQUET_DIR / ALL_YEARS_FILE
    return PARQUET_DIR / f"lol_esports_{year}.parquet"


def ensure_dirs():
    """Cria diretórios necessários se não existirem."""
    for dir_path in [MODELS_DIR, OUTPUTS_DIR, NOTEBOOKS_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Data Dir: {DATA_DIR}")
    print(f"Parquet Dir: {PARQUET_DIR}")
    ensure_dirs()
