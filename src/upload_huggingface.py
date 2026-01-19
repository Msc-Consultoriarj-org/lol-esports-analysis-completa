"""
Upload de dados para HuggingFace Datasets.

Este script faz upload dos arquivos parquet para o HuggingFace Hub,
permitindo acesso fácil via Google Colab e HuggingFace Spaces.
"""

import os
import sys
from pathlib import Path
from typing import Optional, List
import argparse

try:
    from huggingface_hub import HfApi, login, create_repo
    from datasets import Dataset, DatasetDict
    import pandas as pd
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    print("Instale as dependências: pip install huggingface_hub datasets pandas pyarrow")
    sys.exit(1)

# Adiciona o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PARQUET_DIR, HF_DATASET_REPO, YEARS, 
    get_parquet_path, PROJECT_ROOT
)


def upload_to_huggingface(
    repo_id: Optional[str] = None,
    years: Optional[List[int]] = None,
    include_all_years: bool = True,
    private: bool = False,
    token: Optional[str] = None
):
    """
    Faz upload dos dados de LoL Esports para o HuggingFace Hub.
    
    Args:
        repo_id: ID do repositório (user/repo). Default: config.HF_DATASET_REPO
        years: Anos específicos para upload. Default: todos
        include_all_years: Se True, inclui arquivo consolidado
        private: Se True, cria repositório privado
        token: Token do HuggingFace. Se None, usa variável de ambiente
    """
    repo_id = repo_id or HF_DATASET_REPO
    years = years or YEARS
    
    print(f"🚀 Iniciando upload para HuggingFace: {repo_id}")
    print(f"   Anos: {years}")
    print(f"   Incluir ALL_YEARS: {include_all_years}")
    print(f"   Privado: {private}")
    print()
    
    # Autenticação
    if token:
        login(token=token)
    elif os.environ.get("HF_TOKEN"):
        login(token=os.environ["HF_TOKEN"])
    else:
        print("⚠️  Nenhum token encontrado. Use:")
        print("   - Variável de ambiente HF_TOKEN")
        print("   - Argumento --token")
        print("   - huggingface-cli login")
        print()
        login()  # Vai pedir interativamente
    
    api = HfApi()
    
    # Cria o repositório se não existir
    try:
        create_repo(
            repo_id=repo_id,
            repo_type="dataset",
            private=private,
            exist_ok=True
        )
        print(f"✅ Repositório criado/verificado: {repo_id}")
    except Exception as e:
        print(f"⚠️  Erro ao criar repositório: {e}")
    
    # Carrega e faz upload de cada ano
    datasets_dict = {}
    
    for year in years:
        parquet_path = get_parquet_path(year)
        
        if not parquet_path.exists():
            print(f"⏭️  Ano {year}: arquivo não encontrado, pulando...")
            continue
        
        print(f"📤 Carregando {year}...")
        try:
            df = pd.read_parquet(parquet_path)
            dataset = Dataset.from_pandas(df)
            datasets_dict[f"year_{year}"] = dataset
            print(f"   ✅ {len(df):,} registros carregados")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
    
    # Arquivo ALL_YEARS
    if include_all_years:
        all_years_path = get_parquet_path("ALL_YEARS")
        
        if all_years_path.exists():
            print(f"📤 Carregando ALL_YEARS...")
            try:
                df = pd.read_parquet(all_years_path)
                dataset = Dataset.from_pandas(df)
                datasets_dict["all_years"] = dataset
                print(f"   ✅ {len(df):,} registros carregados")
            except Exception as e:
                print(f"   ❌ Erro: {e}")
        else:
            print(f"⏭️  ALL_YEARS: arquivo não encontrado")
    
    if not datasets_dict:
        print("❌ Nenhum dado carregado. Verifique os arquivos parquet.")
        return
    
    # Cria DatasetDict e faz push
    print(f"\n🚀 Fazendo upload de {len(datasets_dict)} splits...")
    
    dataset_dict = DatasetDict(datasets_dict)
    
    try:
        dataset_dict.push_to_hub(
            repo_id=repo_id,
            private=private,
        )
        print(f"\n✅ Upload completo!")
        print(f"📎 URL: https://huggingface.co/datasets/{repo_id}")
    except Exception as e:
        print(f"\n❌ Erro no upload: {e}")
        raise


def upload_parquet_files_directly(
    repo_id: Optional[str] = None,
    token: Optional[str] = None,
    private: bool = False
):
    """
    Faz upload dos arquivos parquet diretamente (sem converter para Dataset).
    Mais rápido para arquivos grandes.
    
    Args:
        repo_id: ID do repositório
        token: Token do HuggingFace
        private: Se True, cria repositório privado
    """
    repo_id = repo_id or HF_DATASET_REPO
    
    print(f"🚀 Upload direto de arquivos parquet para: {repo_id}")
    
    # Autenticação
    if token:
        login(token=token)
    elif os.environ.get("HF_TOKEN"):
        login(token=os.environ["HF_TOKEN"])
    else:
        login()
    
    api = HfApi()
    
    # Cria repositório
    try:
        create_repo(
            repo_id=repo_id,
            repo_type="dataset",
            private=private,
            exist_ok=True
        )
    except Exception as e:
        print(f"⚠️  {e}")
    
    # Lista arquivos parquet
    parquet_files = list(PARQUET_DIR.glob("*.parquet"))
    
    if not parquet_files:
        print(f"❌ Nenhum arquivo parquet encontrado em {PARQUET_DIR}")
        return
    
    print(f"📁 Encontrados {len(parquet_files)} arquivos")
    
    # Upload de cada arquivo
    for pq_file in parquet_files:
        print(f"📤 Uploading {pq_file.name}...")
        try:
            api.upload_file(
                path_or_fileobj=str(pq_file),
                path_in_repo=f"data/{pq_file.name}",
                repo_id=repo_id,
                repo_type="dataset"
            )
            print(f"   ✅ {pq_file.name} uploaded")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
    
    # Cria README para o dataset
    readme_content = create_dataset_readme(repo_id, parquet_files)
    
    readme_path = PROJECT_ROOT / "dataset_readme.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    try:
        api.upload_file(
            path_or_fileobj=str(readme_path),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="dataset"
        )
        print("✅ README.md uploaded")
    except Exception as e:
        print(f"⚠️  Erro no README: {e}")
    
    # Remove arquivo temporário
    readme_path.unlink(missing_ok=True)
    
    print(f"\n✅ Upload completo!")
    print(f"📎 URL: https://huggingface.co/datasets/{repo_id}")


def create_dataset_readme(repo_id: str, parquet_files: List[Path]) -> str:
    """Cria README para o dataset no HuggingFace."""
    
    files_list = "\n".join([f"- `{f.name}`" for f in sorted(parquet_files)])
    
    readme = f"""---
license: cc-by-4.0
task_categories:
  - tabular-classification
language:
  - en
tags:
  - esports
  - league-of-legends
  - competitive-gaming
  - match-prediction
size_categories:
  - 1M<n<10M
---

# LoL Esports Match Data

Comprehensive dataset of professional League of Legends esports matches from 2014-2026.

## Dataset Description

This dataset contains match-level and player-level statistics from professional LoL esports competitions worldwide, sourced from Oracle's Elixir.

### Data Files

{files_list}

## Dataset Structure

### Columns

- **Match Identification**: `gameid`, `league`, `year`, `split`, `playoffs`, `date`, `game`, `patch`
- **Participant Info**: `participantid`, `side`, `position`, `playername`, `playerid`, `teamname`, `teamid`, `champion`
- **Draft**: `ban1-ban5`, `pick1-pick5`
- **Results**: `result` (1=win, 0=loss), `gamelength`
- **Objectives**: `firstblood`, `firstdragon`, `firstherald`, `firstbaron`, `firsttower`, `dragons`, `barons`, etc.
- **Economy**: `totalgold`, `earnedgold`, `goldat10/15/20/25`, `golddiffat10/15/20/25`
- **Combat**: `kills`, `deaths`, `assists`, `damagetochampions`, `dpm`
- **Vision**: `wardsplaced`, `wardskilled`, `visionscore`

### Statistics

- **Total Records**: ~1.1M
- **Unique Matches**: ~93,000
- **Years**: 2014-2026
- **Leagues**: 120+
- **Teams**: 2,300+
- **Players**: 11,000+
- **Champions**: 172

## Usage

```python
from datasets import load_dataset

# Load all years
dataset = load_dataset("{repo_id}", split="all_years")

# Load specific year
dataset_2025 = load_dataset("{repo_id}", split="year_2025")

# Convert to pandas
df = dataset.to_pandas()
```

## Source

Data sourced from [Oracle's Elixir](https://oracleselixir.com/).

## License

CC-BY-4.0
"""
    return readme


def main():
    """CLI principal."""
    parser = argparse.ArgumentParser(
        description="Upload LoL Esports data to HuggingFace Hub"
    )
    
    parser.add_argument(
        "--repo",
        type=str,
        default=HF_DATASET_REPO,
        help=f"Repository ID (default: {HF_DATASET_REPO})"
    )
    
    parser.add_argument(
        "--token",
        type=str,
        help="HuggingFace token (or set HF_TOKEN env var)"
    )
    
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        help="Specific years to upload (default: all)"
    )
    
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create private repository"
    )
    
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Upload parquet files directly (faster for large files)"
    )
    
    args = parser.parse_args()
    
    if args.direct:
        upload_parquet_files_directly(
            repo_id=args.repo,
            token=args.token,
            private=args.private
        )
    else:
        upload_to_huggingface(
            repo_id=args.repo,
            years=args.years,
            token=args.token,
            private=args.private
        )


if __name__ == "__main__":
    main()
