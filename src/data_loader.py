"""
Data Loader - Carregamento de dados de partidas de LoL Esports.

Suporta carregamento local (parquet) e HuggingFace Datasets.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Union
import warnings

try:
    from datasets import load_dataset, Dataset
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    warnings.warn("HuggingFace datasets não instalado. Use: pip install datasets")

from .config import (
    PARQUET_DIR, get_parquet_path, YEARS,
    HF_DATASET_REPO, ID_COLUMNS, TARGET_COLUMN
)


class LoLDataLoader:
    """
    Carregador de dados de LoL Esports.
    
    Suporta múltiplas fontes:
    - Arquivos Parquet locais
    - HuggingFace Datasets
    
    Exemplos:
        >>> loader = LoLDataLoader()
        >>> df = loader.load_year(2025)
        >>> df_all = loader.load_all_years()
        >>> df_range = loader.load_years(2022, 2026)
    """
    
    def __init__(self, use_huggingface: bool = False):
        """
        Inicializa o loader.
        
        Args:
            use_huggingface: Se True, carrega do HuggingFace Hub.
        """
        self.use_huggingface = use_huggingface
        self._cache = {}
        
    def load_year(self, year: int, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Carrega dados de um ano específico.
        
        Args:
            year: Ano (2014-2026)
            columns: Colunas específicas para carregar (otimização)
            
        Returns:
            DataFrame com os dados do ano
        """
        if year not in YEARS:
            raise ValueError(f"Ano {year} não disponível. Anos válidos: {YEARS}")
        
        cache_key = f"{year}_{columns}"
        if cache_key in self._cache:
            return self._cache[cache_key].copy()
        
        if self.use_huggingface and HF_AVAILABLE:
            df = self._load_from_huggingface(year, columns)
        else:
            df = self._load_from_parquet(year, columns)
        
        self._cache[cache_key] = df
        return df.copy()
    
    def load_all_years(self, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Carrega o dataset consolidado com todos os anos.
        
        Args:
            columns: Colunas específicas para carregar
            
        Returns:
            DataFrame com todos os dados (2014-2026)
        """
        if self.use_huggingface and HF_AVAILABLE:
            return self._load_from_huggingface("ALL_YEARS", columns)
        
        parquet_path = get_parquet_path("ALL_YEARS")
        if parquet_path.exists():
            return pd.read_parquet(parquet_path, columns=columns)
        
        # Fallback: concatenar anos individuais
        print("Arquivo ALL_YEARS não encontrado. Concatenando anos...")
        dfs = []
        for year in YEARS:
            try:
                df = self.load_year(year, columns)
                dfs.append(df)
            except FileNotFoundError:
                print(f"  Ano {year} não encontrado, pulando...")
        
        return pd.concat(dfs, ignore_index=True)
    
    def load_years(
        self, 
        start_year: int, 
        end_year: int, 
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Carrega dados de um intervalo de anos.
        
        Args:
            start_year: Ano inicial (incluso)
            end_year: Ano final (incluso)
            columns: Colunas específicas
            
        Returns:
            DataFrame com dados do intervalo
        """
        dfs = []
        for year in range(start_year, end_year + 1):
            if year in YEARS:
                try:
                    df = self.load_year(year, columns)
                    dfs.append(df)
                except FileNotFoundError:
                    print(f"  Ano {year} não encontrado, pulando...")
        
        if not dfs:
            raise ValueError(f"Nenhum dado encontrado para {start_year}-{end_year}")
        
        return pd.concat(dfs, ignore_index=True)
    
    def load_recent(
        self, 
        n_years: int = 3, 
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Carrega os N anos mais recentes.
        
        Args:
            n_years: Número de anos recentes
            columns: Colunas específicas
            
        Returns:
            DataFrame com dados recentes
        """
        recent_years = sorted(YEARS, reverse=True)[:n_years]
        return self.load_years(min(recent_years), max(recent_years), columns)
    
    def _load_from_parquet(
        self, 
        year: Union[int, str], 
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Carrega de arquivo parquet local."""
        parquet_path = get_parquet_path(year)
        
        if not parquet_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {parquet_path}")
        
        return pd.read_parquet(parquet_path, columns=columns)
    
    def _load_from_huggingface(
        self, 
        year: Union[int, str], 
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Carrega do HuggingFace Datasets."""
        if not HF_AVAILABLE:
            raise ImportError("HuggingFace datasets não instalado")
        
        # Define qual split carregar
        split = "all_years" if year == "ALL_YEARS" else f"year_{year}"
        
        try:
            dataset = load_dataset(HF_DATASET_REPO, split=split)
            df = dataset.to_pandas()
            
            if columns:
                df = df[columns]
            
            return df
        except Exception as e:
            print(f"Erro ao carregar do HuggingFace: {e}")
            print("Tentando carregar localmente...")
            return self._load_from_parquet(year, columns)
    
    def get_team_data(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Filtra apenas linhas de dados agregados por time (position == 'team').
        
        Args:
            df: DataFrame de entrada. Se None, carrega todos os anos.
            
        Returns:
            DataFrame apenas com dados de time
        """
        if df is None:
            df = self.load_all_years()
        
        return df[df["position"] == "team"].reset_index(drop=True)
    
    def get_player_data(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Filtra apenas linhas de jogadores individuais.
        
        Args:
            df: DataFrame de entrada. Se None, carrega todos os anos.
            
        Returns:
            DataFrame apenas com dados de jogadores
        """
        if df is None:
            df = self.load_all_years()
        
        return df[df["position"] != "team"].reset_index(drop=True)
    
    def get_matches(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Retorna uma linha por partida (gameid único).
        Útil para análises de match outcome.
        
        Args:
            df: DataFrame de entrada.
            
        Returns:
            DataFrame com uma linha por partida (time vencedor)
        """
        if df is None:
            df = self.load_all_years()
        
        team_df = self.get_team_data(df)
        
        # Pega apenas o time vencedor de cada partida
        return team_df[team_df[TARGET_COLUMN] == 1].reset_index(drop=True)
    
    def clear_cache(self):
        """Limpa o cache de dados."""
        self._cache.clear()
    
    def info(self) -> dict:
        """Retorna informações sobre os dados disponíveis."""
        info = {
            "source": "HuggingFace" if self.use_huggingface else "Local Parquet",
            "years_available": [],
            "total_files": 0,
        }
        
        for year in YEARS:
            path = get_parquet_path(year)
            if path.exists():
                info["years_available"].append(year)
                info["total_files"] += 1
        
        # Verifica ALL_YEARS
        if get_parquet_path("ALL_YEARS").exists():
            info["all_years_available"] = True
            info["total_files"] += 1
        else:
            info["all_years_available"] = False
        
        return info


# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA
# =============================================================================

def load_data(
    year: Optional[int] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    use_huggingface: bool = False,
    columns: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Função de conveniência para carregar dados.
    
    Args:
        year: Ano específico
        start_year: Ano inicial do intervalo
        end_year: Ano final do intervalo
        use_huggingface: Se True, carrega do HuggingFace
        columns: Colunas específicas
        
    Returns:
        DataFrame com os dados
        
    Exemplos:
        >>> df = load_data(year=2025)
        >>> df = load_data(start_year=2022, end_year=2026)
        >>> df = load_data()  # Carrega todos os anos
    """
    loader = LoLDataLoader(use_huggingface=use_huggingface)
    
    if year:
        return loader.load_year(year, columns)
    elif start_year and end_year:
        return loader.load_years(start_year, end_year, columns)
    else:
        return loader.load_all_years(columns)


if __name__ == "__main__":
    # Teste básico
    loader = LoLDataLoader()
    print("Info:", loader.info())
    
    # Tenta carregar 2025
    try:
        df = loader.load_year(2025)
        print(f"\n2025 - Shape: {df.shape}")
        print(f"Colunas: {len(df.columns)}")
        print(f"Partidas únicas: {df['gameid'].nunique()}")
    except Exception as e:
        print(f"Erro: {e}")
