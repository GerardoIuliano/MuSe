import json
import csv
import os
import re
import shutil
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import pandas as pd


def find_code_block_with_line_numbers(source_code: str, target_start_line: int) -> Tuple[Optional[str], Optional[int], Optional[int], str]:
    lines = source_code.splitlines()
    if not (1 <= target_start_line <= len(lines)):
        return None, None, None, f"Linea target ({target_start_line}) non valida."

    pattern = re.compile(r"^\s*(?:function|modifier|constructor|receive|fallback)\b")
    candidates = [i for i, l in enumerate(lines) if pattern.search(l)]

    block_start = next((idx for idx in reversed(candidates) if idx + 1 <= target_start_line), None)
    if block_start is None:
        return None, None, None, f"Impossibile associare la riga {target_start_line} a un blocco."

    brace_start = next((i for i in range(block_start, len(lines)) if '{' in lines[i].split('//')[0]), None)
    if brace_start is None:
        return None, None, None, f"Nessuna '{{' trovata dopo la riga {block_start + 1}."

    brace_level = 0
    for i in range(brace_start, len(lines)):
        for char in lines[i].split('//')[0]:
            if char == '{': brace_level += 1
            elif char == '}': brace_level -= 1
        if brace_level == 0:
            extracted_block = "\n".join(lines[block_start:i + 1])
            return extracted_block, block_start + 1, i + 1, "Success"

    return None, None, None, "Parentesi graffe non bilanciate."

def extract_function_from_mutations_original_block(input_csv_path, output_csv_path, row_limit=None):
    output_column = 'ExtractedFunctionOriginal'

    with open(input_csv_path, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        rows = list(reader)[:row_limit] if row_limit else list(reader)

    fieldnames = reader.fieldnames or []
    for col in [output_column, 'StartLineFunction', 'EndLineFunction']:
        if col not in fieldnames:
            fieldnames.append(col)

    os.makedirs(os.path.dirname(output_csv_path) or '.', exist_ok=True)
    error_count = 0

    with open(output_csv_path, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(
            outfile,
            fieldnames=fieldnames,
            lineterminator='\n',
            quoting=csv.QUOTE_ALL,
            escapechar='\\',
            doublequote=True
        )
        writer.writeheader()
        for idx, row in enumerate(rows):
            try:
                path, start_line = row['File'].strip(), int(row['StartLine'].strip())
                if not os.path.isfile(path):
                    raise FileNotFoundError(f"File non trovato: {path}")
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    code = f.read()

                extracted, new_start, new_end, status = find_code_block_with_line_numbers(code, start_line)
                row[output_column] = extracted if status == "Success" else status
                if status == "Success":
                    row['StartLineFunction'] = str(new_start)
                    row['EndLineFunction'] = str(new_end)
                else:
                    error_count += 1
            except Exception as e:
                row[output_column] = f"Errore Riga {idx+2}: {type(e).__name__}: {e}"
                error_count += 1
            writer.writerow(row)

    print(f"Processo completato. Errori riscontrati: {error_count}")


def extract_function_from_mutations_hash_block(input_csv_path, output_csv_path, contracts_dir, filters: Optional[Dict[str, Any]] = None, row_limit: Optional[int] = None):
    required_cols = ['Hash', 'StartLine']
    output_col = 'ExtractedFunctionMutation'

    with open(input_csv_path, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        rows = list(reader)
        if filters:
            rows = [r for r in rows if all(
                r.get(k) in v if isinstance(v, (list, set, tuple)) else r.get(k) == v for k, v in filters.items()
            )]
        if row_limit:
            rows = rows[:row_limit]

    fieldnames = reader.fieldnames or []
    if output_col not in fieldnames:
        fieldnames.append(output_col)
    if 'StartLineFunction' not in fieldnames:
        fieldnames.append('StartLineFunction')
    if 'EndLineFunction' not in fieldnames:
        fieldnames.append('EndLineFunction')

    sol_files = [os.path.join(dp, f) for dp, _, files in os.walk(contracts_dir) for f in files if f.endswith('.sol')]
    os.makedirs(os.path.dirname(output_csv_path) or '.', exist_ok=True)
    error_count = 0

    with open(output_csv_path, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(
            outfile,
            fieldnames=fieldnames,
            lineterminator='\n',
            quoting=csv.QUOTE_ALL,
            escapechar='\\',
            doublequote=True
        )
        writer.writeheader()
        for idx, row in enumerate(rows):
            try:
                h, sl = row['Hash'].strip(), int(row['StartLine'].strip())
                file_path = next((p for p in sol_files if h in os.path.basename(p)), None)
                if not file_path:
                    raise FileNotFoundError(f"Hash {h} non trovato in nomi file.")
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    code = f.read()

                extracted, start_line, end_line, status = find_code_block_with_line_numbers(code, sl)
                row[output_col] = extracted if status.startswith("Success") else status
                if status.startswith("Success"):
                    row['StartLineFunction'] = str(start_line)
                    row['EndLineFunction'] = str(end_line)
                else:
                    error_count += 1
            except Exception as e:
                row[output_col] = f"Errore Riga {idx+2}: {type(e).__name__}: {e}"
                error_count += 1
            writer.writerow(row)

    print(f"Processo completato. Errori riscontrati: {error_count}")




def filter_csv_per_operator(percorso_csv_input, operatore, percorso_csv_output):
    """
    Legge un CSV, filtra le righe per il valore della colonna 'Operator',
    prende le prime 100 righe del filtro, e salva il risultato in un nuovo CSV.

    Args:
        percorso_csv_input (str): Il percorso del file CSV di input.
        operatore (str): Il valore della colonna 'Operator' da filtrare.
        percorso_csv_output (str): Il percorso dove salvare il nuovo CSV troncato.
    """
    try:
        # Leggi il CSV
        df = pd.read_csv(percorso_csv_input)

        # Filtra per la colonna 'Operator'
        df_filtrato = df[df['Operator'] == operatore]

        # Prendi le prime 100 righe
        df_troncato = df_filtrato.head(100)

        # Salva in un nuovo CSV
        df_troncato.to_csv(percorso_csv_output, index=False)

        print(f"CSV salvato con successo in: {percorso_csv_output}")

    except Exception as e:
        print(f"Errore durante l'elaborazione del file: {e}")


def extract_findings_original_ranged(json_dir_path, input_csv_path, output_csv_path, use_function_lines=False):
    base_path = Path(json_dir_path)
    input_data = pd.read_csv(input_csv_path)
    findings_list = []

    for _, row in input_data.iterrows():
        file_path = row["File"]

        if use_function_lines:
            start_line = int(row["StartLineFunction"])
            end_line = int(row["EndLineFunction"])
        else:
            start_line = int(row["StartLine"])
            end_line = int(row["EndLine"])

        file_name = os.path.basename(file_path)
        folder_name = file_name
        contract_folder = base_path / folder_name

        findings_counter = defaultdict(int)

        if not contract_folder.is_dir():
            print(f"⚠️  Cartella non trovata: {folder_name}")
            findings_list.append("Analysis failed")
            continue

        result_tar_path = contract_folder / "result.tar"
        if not result_tar_path.exists():
            print(f"⚠️  result.tar non trovato in: {folder_name}")
            findings_list.append("Analysis failed")
            continue

        try:
            with tarfile.open(result_tar_path, "r") as tar:
                output_json_file = next(
                    (m for m in tar.getmembers() if m.name.endswith("output.json")),
                    None
                )
                if not output_json_file:
                    print(f"⚠️  output.json mancante in {folder_name}")
                    findings_list.append("Analysis failed")
                    continue

                extracted = tar.extractfile(output_json_file)
                data = json.load(extracted)

            detectors = data.get("results", {}).get("detectors", [])
            for detector in detectors:
                for element in detector.get("elements", []):
                    element_lines = element.get("source_mapping", {}).get("lines", [])
                    if not element_lines:
                        continue
                    if any(start_line <= line <= end_line for line in element_lines):
                        check_type = detector.get("check")
                        if check_type:
                            findings_counter[check_type] += 1
                        break

            findings_json = json.dumps(findings_counter) if findings_counter else "{}"
            findings_list.append(findings_json)

        except Exception as e:
            print(f"❌ Errore nel file {result_tar_path}: {e}")
            findings_list.append("Analysis failed")

    input_data["findings_original"] = findings_list
    input_data.to_csv(output_csv_path, index=False)
    print(f"\n✅ CSV aggiornato generato con successo: {output_csv_path}")


def extract_findings_mutated_ranged(json_dir_path, input_csv_path, output_csv_path, use_function_lines=False):
    base_path = Path(json_dir_path)
    input_data = pd.read_csv(input_csv_path)
    findings_list = []

    for _, row in input_data.iterrows():
        file_path = row["File"]
        hash_value = row["Hash"]

        if use_function_lines:
            start_line = int(row["StartLineFunction"])
            end_line = int(row["EndLineFunction"])
        else:
            start_line = int(row["StartLine"])
            end_line = int(row["EndLine"])

        file_name = os.path.basename(file_path)
        folder_name = f"{file_name}-{hash_value}.sol"
        contract_folder = base_path / folder_name

        findings_counter = defaultdict(int)

        if not contract_folder.is_dir():
            print(f"⚠️  Cartella non trovata: {folder_name}")
            findings_list.append("Analysis failed")
            continue

        result_tar_path = contract_folder / "result.tar"
        if not result_tar_path.exists():
            print(f"⚠️  result.tar non trovato in: {folder_name}")
            findings_list.append("Analysis failed")
            continue

        try:
            with tarfile.open(result_tar_path, "r") as tar:
                output_json_file = next(
                    (m for m in tar.getmembers() if m.name.endswith("output.json")),
                    None
                )
                if not output_json_file:
                    print(f"⚠️  output.json mancante in {folder_name}")
                    findings_list.append("Analysis failed")
                    continue

                extracted = tar.extractfile(output_json_file)
                data = json.load(extracted)

            detectors = data.get("results", {}).get("detectors", [])
            for detector in detectors:
                for element in detector.get("elements", []):
                    element_lines = element.get("source_mapping", {}).get("lines", [])
                    if not element_lines:
                        continue
                    if any(start_line <= line <= end_line for line in element_lines):
                        check_type = detector.get("check")
                        if check_type:
                            findings_counter[check_type] += 1
                        break

            findings_json = json.dumps(findings_counter) if findings_counter else "{}"
            findings_list.append(findings_json)

        except Exception as e:
            print(f"❌ Errore nel file {result_tar_path}: {e}")
            findings_list.append("Analysis failed")

    input_data["findings_mutated"] = findings_list
    input_data.to_csv(output_csv_path, index=False)
    print(f"\n✅ CSV aggiornato generato con successo: {output_csv_path}")


# This function should work as one, replacing the two function before
def extract_findings_ranged(json_dir_path, input_csv_path, output_csv_path, mode, use_function_lines=False):
    base_path = Path(json_dir_path)
    input_data = pd.read_csv(input_csv_path, dtype=str, keep_default_na=False)
    findings_list = []

    for _, row in input_data.iterrows():
        if mode == 3:
            if str(row.get("FunctionRefactored", "")).strip().lower() == "empty":
                findings_list.append("N/A")
                continue
            refactored_base_path = Path(json_dir_path)
            contract_mutated_name = row["ContractMutated"]
            contract_folder = refactored_base_path / contract_mutated_name

            try:
                start_line = int(row["StartLineRefactored"])
                end_line = int(row["EndLineRefactored"])
            except (ValueError, TypeError):
                findings_list.append("N/A")
                continue
        else:
            try:
                start_line = int(row["StartLineFunction"] if use_function_lines else row["StartLine"])
                end_line = int(row["EndLineFunction"] if use_function_lines else row["EndLine"])
            except (ValueError, TypeError):
                findings_list.append("Invalid lines")
                continue

            file_path = row["File"]
            file_name = os.path.basename(file_path)

            if mode == 1:
                folder_name = file_name
            elif mode == 2:
                hash_value = row["Hash"]
                folder_name = f"{file_name}-{hash_value}.sol"
            else:
                raise ValueError("Parametro 'mode' non valido.")

            contract_folder = base_path / folder_name

        findings_counter = defaultdict(int)

        result_tar_path = contract_folder / "result.tar"
        if not result_tar_path.exists():
            findings_list.append("Analysis failed")
            continue

        try:
            with tarfile.open(result_tar_path, "r") as tar:
                output_json_file = next((m for m in tar.getmembers() if m.name.endswith("output.json")), None)
                if not output_json_file:
                    findings_list.append("Analysis failed")
                    continue
                extracted = tar.extractfile(output_json_file)
                data = json.load(extracted)

            detectors = data.get("results", {}).get("detectors", [])
            for detector in detectors:
                for element in detector.get("elements", []):
                    element_lines = element.get("source_mapping", {}).get("lines", [])
                    if not element_lines:
                        continue
                    if any(start_line <= line <= end_line for line in element_lines):
                        check_type = detector.get("check")
                        if check_type:
                            findings_counter[check_type] += 1
                        break

            findings_json = json.dumps(findings_counter) if findings_counter else "{}"
            findings_list.append(findings_json)
        except Exception:
            findings_list.append("Analysis failed")

    column_name = {
        1: "findings_original",
        2: "findings_mutated",
        3: "FindingsRefactored"
    }[mode]

    if mode == 3:
        insert_after_col = "FindingsLLM"
        insert_idx = input_data.columns.get_loc(insert_after_col) + 1 if insert_after_col in input_data.columns else len(input_data.columns)
        input_data.insert(loc=insert_idx, column=column_name, value=findings_list)
    else:
        input_data[column_name] = findings_list

    with tempfile.NamedTemporaryFile("w", delete=False, newline='', suffix=".csv") as tmp_file:
        tmp_path = tmp_file.name
        input_data.to_csv(tmp_path, index=False)

    shutil.move(tmp_path, output_csv_path)
    print(f"\n✅ CSV aggiornato generato con successo: {output_csv_path}")



def parse_findings(findings_str):
    """Parses a findings string like '"check": 2, "other": 1' into a dict."""
    findings = defaultdict(int)
    if pd.isna(findings_str) or not str(findings_str).strip():
        return findings
    pattern = r'"([^"]+)":\s*(-?\d+)'
    for check, value in re.findall(pattern, findings_str):
        findings[check] += int(value)
    return findings


def compute_diff(baseline, result):
    """Returns dict of differences between baseline and result findings."""
    diff = {}
    all_keys = set(baseline) | set(result)
    for key in all_keys:
        base_val = baseline.get(key, 0)
        res_val = result.get(key, 0)
        delta = res_val - base_val
        if delta != 0:
            diff[key] = delta
    return diff


def process_findings_diff_single_csv(input_csv, output_csv):
    """
    Adds a 'differences' column to the original CSV by comparing 'findings_original' and 'findings_mutated'.
    The result is saved in the same structure as the input, with one new column.
    """
    df = pd.read_csv(input_csv)
    df.columns = df.columns.str.strip().str.lower()

    diffs = []
    for _, row in df.iterrows():
        findings_orig_str = str(row.get("findings_original", "")).strip()
        findings_mut_str = str(row.get("findings_mutated", "")).strip()

        findings_orig = parse_findings(findings_orig_str)
        findings_mut = parse_findings(findings_mut_str)

        diff = compute_diff(findings_orig, findings_mut)
        diffs.append(json.dumps(diff, ensure_ascii=False))

    df["differences"] = diffs
    df.to_csv(output_csv, index=False)
    # print(f"✅ Output saved with 'differences' column to: {output_csv}")



def csv_beautifier(input_file: str):
    # Carica il file CSV
    df = pd.read_csv(input_file)

    # Rimuove colonne inutili se presenti
    df = df.drop(columns=[col for col in ["start", "end", "status", "time(ms)"] if col in df.columns])

    # Aggiunge ContractOriginal e ContractMutated
    df["ContractOriginal"] = df["file"].apply(lambda x: os.path.basename(x))
    df["ContractMutated"] = df.apply(lambda row: f"{os.path.basename(row['file'])}-{row['hash']}.sol", axis=1)

    # Rimuove colonne non più necessarie
    df = df.drop(columns=["file", "hash"])

    # Rinomina colonne per consistenza
    df = df.rename(columns={
        "operator": "Operator",
        "original": "Original",
        "replacement": "Replacement",
        "startline": "StartLineMutation",
        "endline": "EndLineMutation",
        "extractedfunctionoriginal": "FunctionOriginal",
        "extractedfunctionmutation": "FunctionMutation",
        "startlinefunction": "StartLineFunction",
        "endlinefunction": "EndLineFunction",
        "findings_original": "FindingsOriginal",
        "findings_mutated": "FindingsMutated",
        "differences": "Differences"
    })

    # Imposta 'N/A' per Replacement e ExtractedFunctionMutation se Operator è 'LE'
    if "Operator" in df.columns:
        df.loc[df["Operator"] == "LE", ["Replacement", "FunctionMutation"]] = "N/A"

    # Ordine finale delle colonne
    final_columns = [
        "ContractOriginal", "ContractMutated", "Operator", "Original", "Replacement",
        "StartLineMutation", "EndLineMutation", "FunctionOriginal", "FunctionMutation",
        "StartLineFunction", "EndLineFunction", "FindingsOriginal", "FindingsMutated", "Differences"
    ]
    df = df[[col for col in final_columns if col in df.columns]]

    # Salva il file sovrascrivendo quello originale
    df.to_csv(input_file, index=False)



def count_analysis_failed_mismatches_by_operator(csv_path):
    df = pd.read_csv(csv_path)

    # Normalizza le colonne findings
    original_clean = df["findings_original"].astype(str).str.strip().str.lower()
    mutated_clean = df["findings_mutated"].astype(str).str.strip().str.lower()

    # Condizione: solo findings_mutated è "analysis failed"
    condition = (original_clean != "analysis failed") & (mutated_clean == "analysis failed")
    mismatches = df[condition]

    if mismatches.empty:
        print("✅ Nessun mismatch trovato.")
    else:
        print(f"⚠️ Trovati {len(mismatches)} mismatch in cui solo 'findings_mutated' è 'Analysis failed'.")
        counts = mismatches["operator"].value_counts()

        print("\n🔢 Mismatch per operatore:")
        for operator, count in counts.items():
            print(f"  {operator}: {count}")


def drop_failed_cases(file_path: str) -> None:
    """
    Filtra un CSV eliminando le righe in cui:
    - FindingsMutated == 'Analysis Failed'
    - FindingsOriginal != 'Analysis Failed'

    Sovrascrive il file originale con i dati filtrati.
    """
    # Legge il CSV
    df = pd.read_csv(file_path)

    # Applica il filtro
    filtered_df = df[~((df['FindingsMutated'] == 'Analysis failed') &
                       (df['FindingsOriginal'] != 'Analysis failed'))]

    # Sovrascrive il file con i dati filtrati
    filtered_df.to_csv(file_path, index=False)
    # print(f"File sovrascritto con i dati filtrati: {file_path}")


def count_clean_functions(csv_path):
    """
    Conta e stampa quante volte il valore '{}' appare nella colonna 'FindingsOriginal' di un file CSV,
    e stampa anche il numero di occorrenze per ciascun valore unico della colonna 'Operator'.

    Args:
        csv_path (str): Percorso del file CSV.
    """
    try:
        df = pd.read_csv(csv_path)

        if "FindingsOriginal" not in df.columns:
            raise ValueError("La colonna 'FindingsOriginal' non è presente nel file CSV.")
        if "Operator" not in df.columns:
            raise ValueError("La colonna 'Operator' non è presente nel file CSV.")

        filtered_df = df[df["FindingsOriginal"] == "{}"]
        total_count = len(filtered_df)
        print(f"\nTotale funzioni pulite: {total_count}")

        operator_counts = filtered_df["Operator"].value_counts()

        print("Conteggio per mutatore:")
        for operator, count in operator_counts.items():
            print(f" {operator}: {count}")

    except Exception as e:
        print(f"Errore durante la lettura del file: {e}")


def filter_by_clean_functions(input_file, output_file):
    """
    Filtra le righe di un CSV in cui la colonna 'FindingsOriginal' ha valore '{}'.

    Args:
        input_file (str): Percorso del file CSV di input.
        output_file (str): Percorso dove salvare il file CSV filtrato.
    """
    with open(input_file, mode='r', newline='', encoding='utf-8') as infile, \
            open(output_file, mode='w', newline='', encoding='utf-8') as outfile:

        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)

        writer.writeheader()
        for row in reader:
            if row.get("FindingsOriginal") == "{}":
                writer.writerow(row)


def csv_to_jsonl(csv_file_path, jsonl_file_path):
    """
    Converte un file CSV in formato JSONL.

    Args:
        csv_file_path (str): Percorso del file CSV di input.
        jsonl_file_path (str): Percorso del file JSONL di output.
    """
    with open(csv_file_path, mode='r', encoding='utf-8') as csv_file, \
            open(jsonl_file_path, mode='w', encoding='utf-8') as jsonl_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            jsonl_file.write(json.dumps(row) + '\n')



def split_csv_by_operator(file_path, min_rows=0):
    # Carica il CSV
    df = pd.read_csv(file_path)

    # Mischia le righe
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    # Estrai il nome base del file
    base_name = os.path.splitext(file_path)[0]

    # Gruppo per "Operator"
    for operator_name, group in df.groupby("Operator"):
        # Scarta gli operatori con meno righe del minimo richiesto
        if len(group) < min_rows:
            print(f"Scartato: {operator_name} (solo {len(group)} righe)")
            continue

        # Calcola la differenza tra EndLineFunction e StartLineFunction
        group["LineDiff"] = group["EndLineFunction"] - group["StartLineFunction"]

        # Righe con diff <= 250
        preferred_rows = group[group["LineDiff"] <= 250]

        # Righe con diff > 250
        fallback_rows = group[group["LineDiff"] > 250]

        # Prova a selezionare 100 righe solo dalle preferred
        sample = preferred_rows.head(100)

        # Se non sono abbastanza, aggiungi dalle fallback
        if len(sample) < 100:
            needed = 100 - len(sample)
            extra_rows = fallback_rows.head(needed)
            sample = pd.concat([sample, extra_rows])

        # Crea un nome file sicuro per l'operatore
        safe_operator_name = "".join(c if c.isalnum() else "_" for c in str(operator_name))

        # Crea il nuovo file
        output_file = f"{base_name}_{safe_operator_name}.csv"
        sample.drop(columns=["LineDiff"], errors="ignore").to_csv(output_file, index=False)
        print(f"Creato: {output_file}")

        # Chiama la funzione per convertire in JSONL
        csv_to_jsonl(output_file, output_file.replace(".csv", ".jsonl"))


def update_csv_with_jsonl(csv_path, jsonl_path, output_path):
    # Leggi il CSV
    df = pd.read_csv(csv_path)

    # Crea un dizionario dal JSONL indicizzato per "ContractMutated"
    jsonl_data = {}
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line)
            key = record.get("ContractMutated")
            if key:
                code = record.get("code")
                if code == "empty":
                    code = "N/A"
                jsonl_data[key] = {
                    "FunctionRefactored": code,
                    "FindingsLLM": record.get("Threats")
                }

    # Mappa i valori sui dati del CSV
    df.insert(
        df.columns.get_loc("FunctionMutation") + 1,
        "FunctionRefactored",
        df["ContractMutated"].map({k: v["FunctionRefactored"] for k, v in jsonl_data.items()})
    )

    df.insert(
        df.columns.get_loc("FindingsMutated") + 1,
        "FindingsLLM",
        df["ContractMutated"].map({k: v["FindingsLLM"] for k, v in jsonl_data.items()})
    )

    # Salva il nuovo CSV
    df.to_csv(output_path, index=False)


def refactor_functions_from_csv(csv_path, input_folder, output_folder, updated_csv_path=None):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Legge il file CSV
    df = pd.read_csv(csv_path, keep_default_na=False)

    # Aggiunge colonne vuote per le nuove righe
    df['StartLineRefactored'] = None
    df['EndLineRefactored'] = None

    for idx, row in df.iterrows():
        filename = row['ContractMutated']
        start_line = int(row['StartLineFunction'])
        end_line = int(row['EndLineFunction'])
        new_function_code = row['FunctionRefactored']

        # Salta se la funzione refactored è mancante, "empty" o "n/a"
        if pd.isna(new_function_code) or str(new_function_code).strip().lower() in ["empty", "n/a"]:
            print(f"Funzione mancante o non valida per {filename}, riga {idx + 2}, nessuna modifica eseguita.")
            df.at[idx, 'StartLineRefactored'] = "N/A"
            df.at[idx, 'EndLineRefactored'] = "N/A"
            continue

        input_file_path = os.path.join(input_folder, filename)
        output_file_path = os.path.join(output_folder, filename)

        # Verifica che il file esista
        if not os.path.isfile(input_file_path):
            print(f"File non trovato: {input_file_path}")
            continue

        with open(input_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        new_function_lines = [line + '\n' for line in str(new_function_code).strip().split('\n')]
        new_start = start_line
        new_end = start_line + len(new_function_lines) - 1

        # Costruisce il nuovo contenuto del file
        updated_lines = (
            lines[:start_line - 1] +
            new_function_lines +
            lines[end_line:]
        )

        # Scrive il file modificato
        with open(output_file_path, 'w', encoding='utf-8') as file:
            file.writelines(updated_lines)

        # Aggiorna il dataframe
        df.at[idx, 'StartLineRefactored'] = new_start
        df.at[idx, 'EndLineRefactored'] = new_end

        print(f"File modificato salvato in: {output_file_path}")

    # Riordina le colonne
    cols = df.columns.tolist()
    end_idx = cols.index('EndLineFunction')
    cols.insert(end_idx + 1, cols.pop(cols.index('StartLineRefactored')))
    cols.insert(end_idx + 2, cols.pop(cols.index('EndLineRefactored')))
    df = df[cols]

    # Salva il CSV aggiornato
    updated_csv_path = updated_csv_path or csv_path
    df.to_csv(updated_csv_path, index=False)
    print(f"CSV aggiornato salvato in: {updated_csv_path}")


##################################################################################################################


mutation_folder = "/Users/matteocicalese/PycharmProjects/MuSe/sumo/results/mutants"
sumo_results = "/Users/matteocicalese/PycharmProjects/MuSe/sumo/results/sumo_results.csv"
contracts_refactored_folder = '/Users/matteocicalese/PycharmProjects/MuSe/contracts_refactored'

slither_results_original = '/Users/matteocicalese/results/slither-0.10.4/slither_original'
slither_results_mutated = '/Users/matteocicalese/results/slither-0.10.4/slither_mutated'
slither_results_refactored = '/Users/matteocicalese/results/slither-0.10.4/slither_refactored'

#file transitori
sumo_results_with_function_original = "/Users/matteocicalese/PycharmProjects/MuSe/intermediate_files/sumo_results_with_functions_original.csv"
sumo_results_with_function_mutation = "/Users/matteocicalese/PycharmProjects/MuSe/intermediate_files/sumo_results_with_functions_mutation.csv"
result_partial1 = '/Users/matteocicalese/PycharmProjects/MuSe/intermediate_files/result_partial1.csv'
result_partial2 = '/Users/matteocicalese/PycharmProjects/MuSe/intermediate_files/result_partial2.csv'
result_final = '/Users/matteocicalese/PycharmProjects/MuSe/intermediate_files/result_final.csv'

result_cleaned = '/Users/matteocicalese/PycharmProjects/MuSe/initial_phase/results.csv'
jsonl_output_results = "/Users/matteocicalese/PycharmProjects/MuSe/initial_phase/results.jsonl"


result_UR1_unprocessed = '/Users/matteocicalese/PycharmProjects/MuSe/initial_phase/results_UR1.csv'
result_UR2_unprocessed = '/Users/matteocicalese/PycharmProjects/MuSe/initial_phase/results_UR2.csv'
result_IUO1_unprocessed = '/Users/matteocicalese/PycharmProjects/MuSe/initial_phase/results_IUO1.csv'
result_TD_unprocessed = '/Users/matteocicalese/PycharmProjects/MuSe/initial_phase/results_TD.csv'
result_TX_unprocessed = '/Users/matteocicalese/PycharmProjects/MuSe/initial_phase/results_TX.csv'
result_CL_unprocessed = '/Users/matteocicalese/PycharmProjects/MuSe/initial_phase/results_CL.csv'

jsonl_UR1 = '/Users/matteocicalese/PycharmProjects/MuSe/input_files/UR1.jsonl'
jsonl_UR2 = '/Users/matteocicalese/PycharmProjects/MuSe/input_files/UR2.jsonl'
jsonl_IUO1 = '/Users/matteocicalese/PycharmProjects/MuSe/input_files/IUO1.jsonl'
jsonl_TD = '/Users/matteocicalese/PycharmProjects/MuSe/input_files/TD.jsonl'
jsonl_TX = '/Users/matteocicalese/PycharmProjects/MuSe/input_files/TX.jsonl'
jsonl_CL = '/Users/matteocicalese/PycharmProjects/MuSe/input_files/CL.jsonl'

output_jsonl_UR1 = '/Users/matteocicalese/PycharmProjects/MuSe/final_phase/results_UR1.jsonl'
output_jsonl_UR2 = '/Users/matteocicalese/PycharmProjects/MuSe/final_phase/results_UR2.jsonl'
output_jsonl_IUO1 = '/Users/matteocicalese/PycharmProjects/MuSe/final_phase/results_IUO1.jsonl'
output_jsonl_TD = '/Users/matteocicalese/PycharmProjects/MuSe/final_phase/results_TD.jsonl'
output_jsonl_TX = '/Users/matteocicalese/PycharmProjects/MuSe/final_phase/results_TX.jsonl'
output_jsonl_CL = '/Users/matteocicalese/PycharmProjects/MuSe/final_phase/results_CL.jsonl'

result_UR1 = '/Users/matteocicalese/PycharmProjects/MuSe/final_phase/results_UR1.csv'
result_UR2 = '/Users/matteocicalese/PycharmProjects/MuSe/final_phase/results_UR2.csv'
result_IUO1 = '/Users/matteocicalese/PycharmProjects/MuSe/final_phase/results_IUO1.csv'
result_TD = '/Users/matteocicalese/PycharmProjects/MuSe/final_phase/results_TD.csv'
result_TX = '/Users/matteocicalese/PycharmProjects/MuSe/final_phase/results_TX.csv'
result_CL = '/Users/matteocicalese/PycharmProjects/MuSe/final_phase/results_CL.csv'


##################################################################################################################


class ResultProcessing:
    def __init__(self):
        extract_function_from_mutations_original_block(sumo_results, sumo_results_with_function_original)
        extract_function_from_mutations_hash_block(sumo_results_with_function_original, sumo_results_with_function_mutation, mutation_folder)

        # extract_findings_original_ranged(slither_results_original, sumo_results_with_function_mutation, result_partial1, use_function_lines=True)
        extract_findings_ranged(slither_results_original, sumo_results_with_function_mutation, result_partial1, use_function_lines=True, mode=1)
        # extract_findings_mutated_ranged(slither_results_mutated, result_partial1, result_partial2, use_function_lines=True)
        extract_findings_ranged(slither_results_mutated, result_partial1, result_partial2, use_function_lines=True, mode=2)

        process_findings_diff_single_csv(result_partial2, result_final)

        count_analysis_failed_mismatches_by_operator(result_final)

        csv_beautifier(result_final)


class DataCleaning:
    def __init__(self):
        drop_failed_cases(result_final)

        count_clean_functions(result_final)

        filter_by_clean_functions(result_final, result_cleaned)


class OutputGeneration:
    def __init__(self):
        csv_to_jsonl(result_cleaned, jsonl_output_results)

        split_csv_by_operator(result_cleaned, min_rows=30)


class FinalAnalysis:
    def __init__(self):
        update_csv_with_jsonl(result_UR1_unprocessed, jsonl_UR1, result_UR1)
        update_csv_with_jsonl(result_UR2_unprocessed, jsonl_UR2, result_UR2)
        update_csv_with_jsonl(result_IUO1_unprocessed, jsonl_IUO1, result_IUO1)
        update_csv_with_jsonl(result_TD_unprocessed, jsonl_TD, result_TD)
        update_csv_with_jsonl(result_TX_unprocessed, jsonl_TX, result_TX)
        update_csv_with_jsonl(result_CL_unprocessed, jsonl_CL, result_CL)

        refactor_functions_from_csv(result_UR1, mutation_folder, contracts_refactored_folder)
        refactor_functions_from_csv(result_UR2, mutation_folder, contracts_refactored_folder)
        refactor_functions_from_csv(result_IUO1, mutation_folder, contracts_refactored_folder)
        refactor_functions_from_csv(result_TD, mutation_folder, contracts_refactored_folder)
        refactor_functions_from_csv(result_TX, mutation_folder, contracts_refactored_folder)
        refactor_functions_from_csv(result_CL, mutation_folder, contracts_refactored_folder)

        extract_findings_ranged(slither_results_refactored, result_UR1, result_UR1, mode=3)
        extract_findings_ranged(slither_results_refactored, result_UR2, result_UR2, mode=3)
        extract_findings_ranged(slither_results_refactored, result_IUO1, result_IUO1, mode=3)
        extract_findings_ranged(slither_results_refactored, result_TD, result_TD, mode=3)
        extract_findings_ranged(slither_results_refactored, result_TX, result_TX, mode=3)
        extract_findings_ranged(slither_results_refactored, result_CL, result_CL, mode=3)

        csv_to_jsonl(result_UR1, output_jsonl_UR1)
        csv_to_jsonl(result_UR2, output_jsonl_UR2)
        csv_to_jsonl(result_IUO1, output_jsonl_IUO1)
        csv_to_jsonl(result_TD, output_jsonl_TD)
        csv_to_jsonl(result_TX, output_jsonl_TX)
        csv_to_jsonl(result_CL, output_jsonl_CL)




ResultProcessing()
DataCleaning()
OutputGeneration()
FinalAnalysis()