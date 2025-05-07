import json
import csv
import os
import re
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Optional, Dict, Any
import pandas as pd


def find_block_regex_and_braces(source_code: str, target_start_line: int):
    lines = source_code.splitlines()
    if not (1 <= target_start_line <= len(lines)):
        return None, f"Linea target ({target_start_line}) non valida."

    pattern = re.compile(r"^\s*(?:function|modifier|constructor|receive|fallback)\b")
    candidates = [i for i, l in enumerate(lines) if pattern.search(l)]
    if not candidates:
        return None, f"Nessuna dichiarazione trovata nel codice."

    block_start = None
    for idx in reversed(candidates):
        if idx + 1 <= target_start_line:
            block_start = idx
            break

    if block_start is None:
        return None, f"Impossibile associare la riga {target_start_line} a un blocco."

    brace_start = None
    for i in range(block_start, len(lines)):
        if '{' in lines[i].split('//')[0]:
            brace_start = i
            break
    if brace_start is None:
        return None, f"Nessuna '{{' trovata dopo la riga {block_start + 1}."

    brace_level = 0
    for i in range(brace_start, len(lines)):
        for char in lines[i].split('//')[0]:
            if char == '{': brace_level += 1
            elif char == '}': brace_level -= 1
        if brace_level == 0:
            block_end = i
            extracted_block = "\n".join(lines[block_start:block_end + 1])
            return extracted_block, "Success"

    return None, "Parentesi graffe non bilanciate."

def process_solidity_csv_regex(input_csv_path, output_csv_path, row_limit=None):
    required_columns = ['File', 'StartLine', 'EndLine']
    output_column = 'ExtractedFunctionOriginal'

    with open(input_csv_path, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        rows = list(reader)[:row_limit] if row_limit else list(reader)

    fieldnames = reader.fieldnames or []
    if output_column not in fieldnames:
        fieldnames.append(output_column)

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
                if not os.path.isfile(path): raise FileNotFoundError(f"File non trovato: {path}")
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    code = f.read()
                extracted, status = find_block_regex_and_braces(code, start_line)
                row[output_column] = extracted if status.startswith("Success") else status
                if not status.startswith("Success"):
                    error_count += 1
            except Exception as e:
                row[output_column] = f"Errore Riga {idx+2}: {type(e).__name__}: {e}"
                error_count += 1
            writer.writerow(row)

    print(f"Processo completato. Errori riscontrati: {error_count}")

def process_solidity_csv_regex_by_hash(input_csv_path, output_csv_path, contracts_dir, filters: Optional[Dict[str, Any]] = None, row_limit: Optional[int] = None):
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
                if not file_path: raise FileNotFoundError(f"Hash {h} non trovato in nomi file.")
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    code = f.read()
                extracted, status = find_block_regex_and_braces(code, sl)
                row[output_col] = extracted if status.startswith("Success") else status
                if not status.startswith("Success"):
                    error_count += 1
            except Exception as e:
                row[output_col] = f"Errore Riga {idx+2}: {type(e).__name__}: {e}"
                error_count += 1
            writer.writerow(row)

    print(f"Processo completato. Errori riscontrati: {error_count}")






def convert_csv_to_json(csv_file_path: str, json_file_path: str) -> None:
    """
    Converts a CSV file to a JSON file where each row is a key-value object.

    Parameters:
    - csv_file_path (str): Path to the input CSV file.
    - json_file_path (str): Path where the output JSON file will be saved.
    """
    try:
        # Load CSV
        df = pd.read_csv(csv_file_path)

        # Convert to list of dictionaries
        data_as_json = df.to_dict(orient="records")

        # Write to JSON file
        with open(json_file_path, "w", encoding="utf-8") as json_file:
            json.dump(data_as_json, json_file, indent=4, ensure_ascii=False)

        print(f"Conversion successful. JSON saved to: {json_file_path}")

    except Exception as e:
        print(f"An error occurred: {e}")


def le_operator_fix(csv_path):
    """
    Reads a CSV file, looks for rows where the 'Operator' column has the value 'LE',
    and sets the value of the 'ExtractedFunctionMutation' column to 'N/A' for those rows.

    !! WARNING !! This function modifies the input CSV file directly (in-place).
    Make a backup of your file before running this if the data is critical.

    Args:
        csv_path (str): The path to the CSV file to read and modify.

    Returns:
        bool: True if the file was successfully modified, False otherwise.

    Raises:
        FileNotFoundError: If the input file is not found (handled internally, returns False).
        KeyError: If the 'Operator' or 'ExtractedFunctionMutation' columns
                  are not present in the CSV file (handled internally, returns False).
        Exception: For other unexpected errors during reading/writing (handled internally).
    """
    modified_data = []
    column_names = []

    operator_column = "Operator"
    target_column = "ExtractedFunctionMutation"
    trigger_value = "LE"
    new_value = "N/A"

    try:
        # --- Step 1: Read the entire file into memory and perform modifications ---
        print(f"Reading data from: {csv_path}...")
        if not os.path.exists(csv_path):
             raise FileNotFoundError(f"Error: Input file not found at '{csv_path}'")

        with open(csv_path, mode='r', newline='', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file)
            column_names = reader.fieldnames
            if not column_names:
                 print(f"Error: CSV file '{csv_path}' appears empty or lacks a header.")
                 return False # Indicate failure
            if operator_column not in column_names:
                raise KeyError(f"Error: Column '{operator_column}' not found in the CSV file.")
            if target_column not in column_names:
                 raise KeyError(f"Error: Column '{target_column}' not found in the CSV file.")

            # Store all rows (modified or not)
            for row in reader:
                if row.get(operator_column, "").strip() == trigger_value:
                    row[target_column] = new_value
                modified_data.append(row)
        print("Data read and modifications prepared.")

        # --- Step 2: Overwrite the original file with the modified data ---
        print(f"Overwriting original file: {csv_path}...")
        with open(csv_path, mode='w', newline='', encoding='utf-8') as output_file:
            # Need column_names obtained during reading
            if not column_names:
                 print("Error: Cannot determine columns for writing.")
                 return False # Should not happen if reading was successful, but safe check

            writer = csv.DictWriter(output_file, fieldnames=column_names)
            writer.writeheader()
            writer.writerows(modified_data)

        print(f"File '{csv_path}' modified successfully in place.")
        return True # Indicate success

    except FileNotFoundError as e:
        print(e)
        return False
    except KeyError as e:
        print(e)
        return False
    except Exception as e:
        print(f"Unexpected error during processing or writing file '{csv_path}': {e}")
        # Consider adding more specific error handling if needed (e.g., permissions)
        return False


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


def extract_findings_original_ranged(json_dir_path, input_csv_path, output_csv_path):
    base_path = Path(json_dir_path)
    input_data = pd.read_csv(input_csv_path)
    findings_list = []

    for _, row in input_data.iterrows():
        file_path = row["File"]
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


def extract_findings_mutated_ranged(json_dir_path, input_csv_path, output_csv_path):
    base_path = Path(json_dir_path)
    input_data = pd.read_csv(input_csv_path)
    findings_list = []

    for _, row in input_data.iterrows():
        file_path = row["File"]
        hash_value = row["Hash"]
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
    print(f"✅ Output saved with 'differences' column to: {output_csv}")


def csv_beautifier(input_file: str):
    # Carica il file CSV
    df = pd.read_csv(input_file)

    # Rimuove le colonne specificate
    columns_to_drop = ["start", "end", "StartLine", "EndLine", "status", "time(ms)"]
    df = df.drop(columns=[col for col in columns_to_drop if col in df.columns])

    # Estrai l'ultima parte del path per ContractOriginal
    df["ContractOriginal"] = df["file"].apply(lambda x: os.path.basename(x))

    # Crea ContractMutated mantenendo l'estensione originale e aggiungendo l'hash
    df["ContractMutated"] = df.apply(lambda row: f"{os.path.basename(row['file'])}-{row['hash']}.sol", axis=1)

    # Rimuove le colonne originali 'file' e 'hash'
    df = df.drop(columns=["file", "hash"])

    # Rinomina colonne specifiche
    rename_map = {
        "findings_original": "FindingsOriginal",
        "findings_mutated": "FindingsMutated",
        "extractedfunctionmutation": "ExtractedFunctionMutation",
        "extractedfunctionoriginal": "ExtractedFunctionOriginal",
        "startline": "StartLine",
        "endline": "EndLine"
    }
    df = df.rename(columns=rename_map)

    # Capitalizza l'iniziale delle altre colonne non già modificate
    df.columns = [col if col in ["ContractOriginal", "ContractMutated"] or col in rename_map.values()
                  else col[0].upper() + col[1:] if col and not col[0].isupper()
                  else col for col in df.columns]

    # Riordina le colonne mettendo 'ContractOriginal' e 'ContractMutated' all'inizio
    cols = ["ContractOriginal", "ContractMutated"] + [col for col in df.columns if col not in ["ContractOriginal", "ContractMutated"]]
    df = df[cols]

    if "Operator" in df.columns:
        df.loc[df["Operator"] == "LE", ["Replacement", "ExtractedFunctionMutation"]] = "N/A"

    # Sovrascrive il file originale con il risultato
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
        print(counts)


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
    filtered_df = df[~((df['FindingsMutated'] == 'Analysis Failed') &
                       (df['FindingsOriginal'] != 'Analysis Failed'))]

    # Sovrascrive il file con i dati filtrati
    filtered_df.to_csv(file_path, index=False)
    print(f"File sovrascritto con i dati filtrati: {file_path}")







sumo_results = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/sumo_results.csv"
sumo_results_with_function_original = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/sumo_results_with_functions_original.csv"
sumo_results_with_function_mutation = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/sumo_results_with_functions_mutation.csv"





sumo_results_filtered = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/sumo_results_filtered.csv"




mutation_folder = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/mutants"
json_output_results = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/results.json"
json_output_results_filtered = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/results_filtered.json"

json_folder_original = '/Users/matteocicalese/results/slither-0.10.4/slither_original'
json_folder_mutated = '/Users/matteocicalese/results/slither-0.10.4/20250506_1751'
result_partial1 = '/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/analysis/result_partial1.csv'
result_partial2 = '/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/analysis/result_partial2.csv'
result_final = '/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/analysis/result_final.csv'


#"""
process_solidity_csv_regex(sumo_results, sumo_results_with_function_original)
process_solidity_csv_regex_by_hash(sumo_results_with_function_original, sumo_results_with_function_mutation, mutation_folder)
#le_operator_fix(sumo_results_with_function_mutation)


extract_findings_original_ranged(json_folder_original, sumo_results_with_function_mutation, result_partial1)
extract_findings_mutated_ranged(json_folder_mutated, result_partial1, result_partial2)
process_findings_diff_single_csv(result_partial2, result_final)

count_analysis_failed_mismatches_by_operator(result_final)

csv_beautifier(result_final)

drop_failed_cases(result_final)


convert_csv_to_json(result_final, json_output_results)
#"""





# filter_csv_per_operator(sumo_results_final, "UTR", sumo_results_filtered)
# convert_csv_to_json(sumo_results_filtered, json_results_filtered)


