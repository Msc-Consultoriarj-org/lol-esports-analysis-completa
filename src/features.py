"""
Feature Engineering - Geração de features para o modelo preditivo.

Este módulo cria features derivadas a partir dos dados brutos,
incluindo estatísticas históricas, métricas de draft e indicadores de performance.
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
import warnings


class FeatureEngineer:
    """
    Engenharia de features para previsão de partidas de LoL.
    
    Gera features em duas categorias:
    1. PRE-GAME: Disponíveis antes da partida (draft, histórico)
    2. IN-GAME: Disponíveis durante/após a partida (gold, objectives)
    
    Exemplos:
        >>> fe = FeatureEngineer()
        >>> df_features = fe.create_all_features(df)
        >>> df_pregame = fe.create_pregame_features(df)
    """
    
    def __init__(self, lookback_matches: int = 20):
        """
        Inicializa o FeatureEngineer.
        
        Args:
            lookback_matches: Número de partidas para calcular médias históricas
        """
        self.lookback_matches = lookback_matches
        self._champion_stats_cache = {}
        self._team_stats_cache = {}
        self._matchup_cache = {}
    
    # =========================================================================
    # PRE-GAME FEATURES (Disponíveis antes da partida)
    # =========================================================================
    
    def create_pregame_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cria features disponíveis antes da partida começar.
        Essas são as features usadas para previsão em tempo real.
        
        Args:
            df: DataFrame com dados de partidas
            
        Returns:
            DataFrame com features pre-game
        """
        df = df.copy()
        
        # 1. Features de lado (Blue/Red)
        df = self._add_side_features(df)
        
        # 2. Features de time (winrate histórico)
        df = self._add_team_historical_features(df)
        
        # 3. Features de campeão
        df = self._add_champion_features(df)
        
        # 4. Features de draft/composição
        df = self._add_draft_features(df)
        
        # 5. Features de liga
        df = self._add_league_features(df)
        
        # 6. Features de patch/meta
        df = self._add_patch_features(df)
        
        return df
    
    def _add_side_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features relacionadas ao lado (Blue/Red)."""
        # Encode side
        df["side_blue"] = (df["side"] == "Blue").astype(int)
        
        # Blue side advantage por liga (calculado historicamente)
        if "league" in df.columns:
            blue_wr_by_league = df[df["position"] == "team"].groupby("league").apply(
                lambda x: x[x["side"] == "Blue"]["result"].mean()
            ).to_dict()
            df["league_blue_advantage"] = df["league"].map(blue_wr_by_league).fillna(0.5)
        
        return df
    
    def _add_team_historical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona winrate histórico do time."""
        # Ordena por data para garantir cálculo correto
        if "date" in df.columns:
            df = df.sort_values("date")
        
        # Calcula winrate rolling para cada time
        team_data = df[df["position"] == "team"].copy()
        
        if len(team_data) > 0:
            # Winrate das últimas N partidas
            team_winrates = {}
            for team in team_data["teamname"].unique():
                team_matches = team_data[team_data["teamname"] == team]["result"]
                rolling_wr = team_matches.rolling(
                    window=self.lookback_matches, min_periods=5
                ).mean()
                team_winrates[team] = rolling_wr.to_dict()
            
            # Mapeia para o DataFrame
            def get_team_wr(row):
                team = row.get("teamname")
                if team in team_winrates:
                    return team_winrates[team].get(row.name, 0.5)
                return 0.5
            
            df["team_historical_wr"] = df.apply(get_team_wr, axis=1)
        else:
            df["team_historical_wr"] = 0.5
        
        return df
    
    def _add_champion_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features de campeões."""
        if "champion" not in df.columns:
            return df
        
        # Winrate global do campeão
        champ_wr = df.groupby("champion")["result"].mean().to_dict()
        df["champion_global_wr"] = df["champion"].map(champ_wr).fillna(0.5)
        
        # Winrate do campeão por liga
        if "league" in df.columns:
            champ_league_wr = df.groupby(["champion", "league"])["result"].mean()
            df["champion_league_wr"] = df.apply(
                lambda x: champ_league_wr.get((x["champion"], x["league"]), 0.5),
                axis=1
            )
        
        # Pickrate do campeão (popularidade)
        total_games = df["gameid"].nunique()
        champ_picks = df["champion"].value_counts() / total_games
        df["champion_pickrate"] = df["champion"].map(champ_picks).fillna(0)
        
        return df
    
    def _add_draft_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features de draft e composição."""
        pick_cols = [f"pick{i}" for i in range(1, 6)]
        ban_cols = [f"ban{i}" for i in range(1, 6)]
        
        # Verifica se tem colunas de draft
        has_picks = all(col in df.columns for col in pick_cols)
        has_bans = all(col in df.columns for col in ban_cols)
        
        if has_picks:
            # Número de campeões "meta" no draft (top 20 winrate)
            if "champion" in df.columns:
                top_champs = df.groupby("champion")["result"].mean().nlargest(20).index.tolist()
                
                def count_meta_picks(row):
                    count = 0
                    for col in pick_cols:
                        if row.get(col) in top_champs:
                            count += 1
                    return count
                
                df["meta_picks_count"] = df.apply(count_meta_picks, axis=1)
        
        if has_bans:
            # Bans direcionados (campeões com alto winrate)
            if "champion" in df.columns:
                high_wr_champs = df.groupby("champion")["result"].mean()
                high_wr_champs = high_wr_champs[high_wr_champs > 0.52].index.tolist()
                
                def count_targeted_bans(row):
                    count = 0
                    for col in ban_cols:
                        if row.get(col) in high_wr_champs:
                            count += 1
                    return count
                
                df["targeted_bans_count"] = df.apply(count_targeted_bans, axis=1)
        
        return df
    
    def _add_league_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features de liga."""
        if "league" not in df.columns:
            return df
        
        # Tier da liga
        tier_map = {
            "LCK": 1, "LPL": 1, "LEC": 1, "LCS": 1,
            "MSI": 0, "Worlds": 0, "WLDs": 0,
            "CBLOL": 2, "LLA": 2, "PCS": 2, "VCS": 2, "LJL": 2
        }
        df["league_tier"] = df["league"].map(tier_map).fillna(3)
        
        # One-hot encoding para ligas principais
        for league in ["LCK", "LPL", "LEC", "LCS"]:
            df[f"is_{league}"] = (df["league"] == league).astype(int)
        
        df["is_international"] = df["league"].isin(["MSI", "Worlds", "WLDs"]).astype(int)
        
        return df
    
    def _add_patch_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features de patch/meta."""
        if "patch" not in df.columns:
            return df
        
        # Extrai versão major e minor do patch
        def parse_patch(patch):
            try:
                parts = str(patch).split(".")
                if len(parts) >= 2:
                    return int(parts[0]), int(parts[1])
                return 0, 0
            except:
                return 0, 0
        
        patch_info = df["patch"].apply(parse_patch)
        df["patch_major"] = patch_info.apply(lambda x: x[0])
        df["patch_minor"] = patch_info.apply(lambda x: x[1])
        
        # Meta freshness (quantos dias desde o patch)
        # Patches mais novos = meta mais instável
        patch_counts = df["patch"].value_counts()
        df["patch_maturity"] = df["patch"].map(patch_counts).fillna(0)
        
        return df
    
    # =========================================================================
    # IN-GAME FEATURES (Disponíveis durante/após a partida)
    # =========================================================================
    
    def create_ingame_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cria features baseadas em eventos in-game.
        Usadas para análise pós-jogo e modelos de tempo real.
        
        Args:
            df: DataFrame com dados de partidas
            
        Returns:
            DataFrame com features in-game
        """
        df = df.copy()
        
        # 1. Features de early game (@10min, @15min)
        df = self._add_early_game_features(df)
        
        # 2. Features de objetivos
        df = self._add_objective_features(df)
        
        # 3. Features de economia
        df = self._add_economy_features(df)
        
        # 4. Features de duração
        df = self._add_duration_features(df)
        
        return df
    
    def _add_early_game_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features de early game."""
        # Gold diff @15 normalizado
        if "golddiffat15" in df.columns:
            df["gold_diff_15_normalized"] = df["golddiffat15"] / 1000  # Em milhares
            df["gold_advantage_15"] = (df["golddiffat15"] > 0).astype(int)
        
        if "golddiffat10" in df.columns:
            df["gold_diff_10_normalized"] = df["golddiffat10"] / 1000
            df["gold_advantage_10"] = (df["golddiffat10"] > 0).astype(int)
        
        # XP diff
        if "xpdiffat15" in df.columns:
            df["xp_diff_15_normalized"] = df["xpdiffat15"] / 1000
        
        # CS diff
        if "csdiffat15" in df.columns:
            df["cs_diff_15_normalized"] = df["csdiffat15"] / 10
        
        return df
    
    def _add_objective_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features de objetivos."""
        first_obj_cols = ["firstblood", "firstdragon", "firstherald", "firstbaron", "firsttower"]
        
        # Conta quantos "first objectives" o time pegou
        available_cols = [col for col in first_obj_cols if col in df.columns]
        if available_cols:
            df["first_objectives_count"] = df[available_cols].sum(axis=1)
            df["first_objectives_ratio"] = df["first_objectives_count"] / len(available_cols)
        
        # Diferença de dragões
        if "dragons" in df.columns and "opp_dragons" in df.columns:
            df["dragon_diff"] = df["dragons"] - df["opp_dragons"]
        
        # Controle de Baron
        if "barons" in df.columns and "opp_barons" in df.columns:
            df["baron_diff"] = df["barons"] - df["opp_barons"]
        
        return df
    
    def _add_economy_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features de economia."""
        # Gold por minuto
        if "totalgold" in df.columns and "gamelength" in df.columns:
            df["gold_per_minute"] = df["totalgold"] / (df["gamelength"] / 60)
        
        # Eficiência de gold (gold earned / total gold)
        if "earnedgold" in df.columns and "totalgold" in df.columns:
            df["gold_efficiency"] = df["earnedgold"] / df["totalgold"].replace(0, 1)
        
        # Damage per gold (eficiência de dano)
        if "damagetochampions" in df.columns and "totalgold" in df.columns:
            df["damage_per_gold"] = df["damagetochampions"] / df["totalgold"].replace(0, 1)
        
        return df
    
    def _add_duration_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features de duração."""
        if "gamelength" not in df.columns:
            return df
        
        # Duração em minutos
        df["game_minutes"] = df["gamelength"] / 60
        
        # Categorias de duração
        df["is_early_game"] = (df["game_minutes"] < 25).astype(int)
        df["is_mid_game"] = ((df["game_minutes"] >= 25) & (df["game_minutes"] < 35)).astype(int)
        df["is_late_game"] = (df["game_minutes"] >= 35).astype(int)
        
        # Bins de duração
        bins = [0, 20, 25, 30, 35, 40, 100]
        labels = ["stomp", "early", "standard", "extended", "late", "ultra_late"]
        df["duration_category"] = pd.cut(df["game_minutes"], bins=bins, labels=labels)
        
        return df
    
    # =========================================================================
    # COMBINED FEATURES
    # =========================================================================
    
    def create_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cria todas as features (pre-game + in-game).
        
        Args:
            df: DataFrame com dados de partidas
            
        Returns:
            DataFrame com todas as features
        """
        df = self.create_pregame_features(df)
        df = self.create_ingame_features(df)
        return df
    
    def get_feature_columns(self, feature_type: str = "all") -> List[str]:
        """
        Retorna lista de colunas de features por tipo.
        
        Args:
            feature_type: "pregame", "ingame", ou "all"
            
        Returns:
            Lista de nomes de colunas
        """
        pregame_features = [
            "side_blue", "league_blue_advantage", "team_historical_wr",
            "champion_global_wr", "champion_league_wr", "champion_pickrate",
            "meta_picks_count", "targeted_bans_count",
            "league_tier", "is_LCK", "is_LPL", "is_LEC", "is_LCS", "is_international",
            "patch_major", "patch_minor", "patch_maturity"
        ]
        
        ingame_features = [
            "gold_diff_15_normalized", "gold_advantage_15",
            "gold_diff_10_normalized", "gold_advantage_10",
            "xp_diff_15_normalized", "cs_diff_15_normalized",
            "first_objectives_count", "first_objectives_ratio",
            "dragon_diff", "baron_diff",
            "gold_per_minute", "gold_efficiency", "damage_per_gold",
            "game_minutes", "is_early_game", "is_mid_game", "is_late_game"
        ]
        
        if feature_type == "pregame":
            return pregame_features
        elif feature_type == "ingame":
            return ingame_features
        else:
            return pregame_features + ingame_features
    
    def create_matchup_features(
        self, 
        df: pd.DataFrame, 
        position: str = "all"
    ) -> pd.DataFrame:
        """
        Cria features de matchup (confronto entre campeões).
        
        Args:
            df: DataFrame com dados de partidas
            position: Posição específica ou "all"
            
        Returns:
            DataFrame com features de matchup
        """
        df = df.copy()
        
        if "champion" not in df.columns or "position" not in df.columns:
            warnings.warn("Colunas 'champion' ou 'position' não encontradas")
            return df
        
        # Filtra por posição se especificado
        if position != "all":
            df_pos = df[df["position"] == position].copy()
        else:
            df_pos = df[df["position"] != "team"].copy()
        
        # Cria matchup string (champ_a vs champ_b, ordenado alfabeticamente)
        # Para isso precisamos identificar os oponentes na mesma partida
        
        # Winrate de matchup histórico
        # (implementação simplificada - em produção seria mais complexo)
        
        return df


# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA
# =============================================================================

def engineer_features(
    df: pd.DataFrame,
    feature_type: str = "all",
    lookback: int = 20
) -> pd.DataFrame:
    """
    Função de conveniência para engenharia de features.
    
    Args:
        df: DataFrame com dados
        feature_type: "pregame", "ingame", ou "all"
        lookback: Janela de lookback para médias históricas
        
    Returns:
        DataFrame com features
    """
    fe = FeatureEngineer(lookback_matches=lookback)
    
    if feature_type == "pregame":
        return fe.create_pregame_features(df)
    elif feature_type == "ingame":
        return fe.create_ingame_features(df)
    else:
        return fe.create_all_features(df)


if __name__ == "__main__":
    # Teste básico
    print("FeatureEngineer inicializado")
    fe = FeatureEngineer()
    print(f"Features pregame: {len(fe.get_feature_columns('pregame'))}")
    print(f"Features ingame: {len(fe.get_feature_columns('ingame'))}")
    print(f"Features total: {len(fe.get_feature_columns('all'))}")
