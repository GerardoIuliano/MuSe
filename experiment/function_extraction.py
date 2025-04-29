import csv
import hashlib
import json
import os
import re # Importato per le espressioni regolari
import argparse

# --- FUNZIONE DI ESTRAZIONE MIGLIORATA BASATA SU REGEX E PARENTESI ---

import csv
import os
import re # Importato per le espressioni regolari
import argparse
import time
from typing import Optional, Dict, Any

import pandas as pd


# --- FUNZIONE DI ESTRAZIONE MIGLIORATA BASATA SU REGEX E PARENTESI ---

def find_block_regex_and_braces(source_code, target_start_line):
    """
    Trova il blocco (function, modifier, constructor, receive, fallback) che contiene la
    target_start_line usando regex per trovare l'inizio della dichiarazione del blocco
    e il conteggio delle parentesi graffe per trovare la fine.

    Gestisce casi in cui la parentesi graffa aperta '{' si trova su una
    riga diversa dalla dichiarazione iniziale e riconosce le funzioni speciali
    receive() e fallback().

    Args:
        source_code (str): Il codice sorgente completo del file Solidity.
        target_start_line (int): La riga (1-based) che deve trovarsi all'interno del blocco.

    Returns:
        tuple: Una tupla contenente:
               - (str | None): Il codice sorgente completo del blocco trovato, o None.
               - (str): Un messaggio di stato ("Success", "Error: ...").
    """
    lines = source_code.splitlines()
    num_lines = len(lines)
    if target_start_line <= 0 or target_start_line > num_lines:
        return None, f"Errore Logico: Target line ({target_start_line}) non valida per file con {num_lines} righe."

    # Pattern Regex per trovare l'inizio della *dichiarazione* di function, modifier, constructor,
    # E ANCHE le funzioni speciali receive e fallback.
    # Non richiede la '{' sulla stessa riga. Usa \b per word boundary.
    # \s*      = zero o più spazi
    # (?:...)  = gruppo non catturante
    # \b       = word boundary (evita match parziali tipo 'myfunction')
    block_declaration_pattern = re.compile(
        r"^\s*(?:function|modifier|constructor|receive|fallback)\b"  # <-- AGGIUNTO receive|fallback
    )

    candidate_starts = []
    for i, line in enumerate(lines):
        line_num = i + 1 # 1-based line number
        if block_declaration_pattern.search(line):
             # Trovato un potenziale inizio di dichiarazione. È prima o sulla target line?
             if line_num <= target_start_line:
                 candidate_starts.append(line_num)

    if not candidate_starts:
        # Prova a cercare ANCHE dopo la target line se nessun candidato trovato prima.
        # Questo gestisce casi rari dove la target line è su un commento/riga vuota *prima* della funzione.
        for i in range(target_start_line - 1, num_lines):
             line_num = i + 1
             if block_declaration_pattern.search(lines[i]):
                 candidate_starts.append(line_num)
                 break # Prendi il primo trovato dopo la target line

        if not candidate_starts:
            # Modificato messaggio per includere receive/fallback
            return None, f"Errore Ricerca: Nessuna dichiarazione (function/modifier/constructor/receive/fallback) trovata vicino alla riga {target_start_line}."


    # Il candidato migliore è l'ultimo trovato <= target_start_line,
    # o il primo trovato > target_start_line se nessun candidato precedente.
    best_declaration_start_line_num = -1
    valid_candidates_before_or_at_target = [l for l in candidate_starts if l <= target_start_line]

    if valid_candidates_before_or_at_target:
        best_declaration_start_line_num = max(valid_candidates_before_or_at_target)
    elif candidate_starts: # Se ci sono candidati, ma tutti dopo la target line
         # Questo scenario è meno probabile se la target line è DENTRO il blocco,
         # ma lo gestiamo prendendo il più vicino (minimo) dopo.
         # Potrebbe indicare un target_line errato nell'input CSV.
         best_declaration_start_line_num = min(candidate_starts)

    if best_declaration_start_line_num == -1:
         # Caso in cui non è stato trovato assolutamente nessun candidato
          return None, f"Errore Logica Candidati: Nessuna dichiarazione valida trovata per riga {target_start_line}."


    declaration_start_line_idx = best_declaration_start_line_num - 1

    # --- Trova la prima parentesi graffa aperta '{' a partire dalla riga di dichiarazione ---
    first_brace_line_idx = -1
    first_brace_char_idx = -1
    found_opening_brace = False

    for i in range(declaration_start_line_idx, num_lines):
        line = lines[i]
        # Ignora commenti semplici (molto basico, può fallire!)
        line_content = line.split('//')[0] # Rimuove commenti //

        brace_pos = line_content.find('{')
        if brace_pos != -1:
            first_brace_line_idx = i
            first_brace_char_idx = brace_pos
            found_opening_brace = True
            break # Trovata la prima '{'

    if not found_opening_brace:
        # Potrebbe essere una dichiarazione senza corpo (interfaccia, abstract) o errore
         return None, f"Errore Ricerca Parentesi: Impossibile trovare '{{' dopo la dichiarazione alla riga {best_declaration_start_line_num}. Forse interfaccia/abstract o dichiarazione incompleta?"


    # --- Conteggio Parentesi Graffe per Trovare la Fine ---
    brace_level = 0
    end_line_idx = -1
    scan_started = False # Indica se abbiamo iniziato a contare dopo aver trovato la prima '{'

    # Inizia la scansione dalla riga dove abbiamo trovato la prima '{'
    for i in range(first_brace_line_idx, num_lines):
        line = lines[i]
        line_content = line.split('//')[0]

        start_char_index = 0
        if i == first_brace_line_idx:
            # Nella riga dove inizia la graffa, inizia a scansionare da quella graffa
            start_char_index = first_brace_char_idx

        for char_idx in range(start_char_index, len(line_content)):
            char = line_content[char_idx]

            if char == '{':
                if not scan_started:
                    # Questa è la prima '{' trovata (quella a first_brace_line_idx, first_brace_char_idx)
                    scan_started = True
                    brace_level = 1
                else:
                    # '{' successive
                    brace_level += 1
            elif char == '}':
                if scan_started: # Ignora '}' se trovate prima della '{' iniziale (improbabile)
                    brace_level -= 1
                    if brace_level == 0:
                        # Trovata la parentesi graffa chiusa corrispondente!
                        end_line_idx = i
                        break # Esci dal loop interno dei caratteri

        if end_line_idx != -1:
            break # Esci dal loop esterno delle righe

    if end_line_idx == -1:
        # Se non abbiamo trovato una graffa di chiusura, c'è un problema
        return None, f"Errore Conteggio Parentesi: Impossibile trovare la '}}' corrispondente per il blocco iniziato alla riga {best_declaration_start_line_num} (graffa aperta trovata alla riga {first_brace_line_idx + 1}). Controllare il codice sorgente per parentesi sbilanciate."

    # --- Estrazione del codice ---
    try:
        # Estrai dalla riga di INIZIO DICHIARAZIONE (declaration_start_line_idx)
        # fino alla riga di fine trovata (end_line_idx) INCLUSA.
        extracted_lines = lines[declaration_start_line_idx : end_line_idx + 1]
        extracted_code = "\n".join(extracted_lines)

        # Piccolo controllo di sanità
        if not extracted_code.strip():
             return None, f"Errore Estrazione: Blocco estratto ({best_declaration_start_line_num}-{end_line_idx+1}) risulta vuoto."

        # Verifica se la target line è effettivamente compresa nel blocco CORRETTAMENTE identificato
        if not (best_declaration_start_line_num <= target_start_line <= end_line_idx + 1):
             # Se questo errore persiste ANCHE CON LA REGEX CORRETTA,
             # significa che la target_start_line fornita nel CSV è GIA'
             # al di fuori del blocco receive/fallback/etc. nel file sorgente.
             # L'estrattore ha funzionato correttamente, ma l'input era "scorretto"
             # rispetto al blocco identificato.
              return None, f"Errore Logico Post-Estrazione: La target line {target_start_line} fornita non è nel blocco identificato {best_declaration_start_line_num}-{end_line_idx+1}. Controllare l'input CSV o il sorgente."

        return extracted_code, "Success (Regex/Brace Count - Improved+Receive/Fallback)"

    except IndexError:
        return None, f"Errore Estrazione: Indici ({declaration_start_line_idx}-{end_line_idx+1}) fuori dai limiti dopo ricerca."
    except Exception as e:
        return None, f"Errore Imprevisto Estrazione: {type(e).__name__}: {e}"


# --- Funzione principale che USA la nuova logica ---
# (Il resto del codice process_solidity_csv_regex e main rimane invariato)
def process_solidity_csv_regex(input_csv_path, output_csv_path, row_limit=None):
    """
    Processa il CSV usando l'estrazione basata su Regex e conteggio parentesi (MIGLIORATA).
    """
    required_columns = ['File', 'StartLine', 'EndLine'] # Manteniamo EndLine per compatibilità input
    output_column_name = 'ExtractedFunctionOriginal'
    processed_data = []
    original_fieldnames = []
    input_data = []

    # --- 1. Lettura CSV e gestione limite (come prima) ---
    if not os.path.exists(input_csv_path):
        print(f"Errore: File CSV di input non trovato: {input_csv_path}")
        return
    try:
        with open(input_csv_path, 'r', newline='', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            if not reader.fieldnames:
                 print(f"Errore: CSV '{input_csv_path}' vuoto o malformato.")
                 return
            original_fieldnames = reader.fieldnames
            if not all(col in original_fieldnames for col in required_columns):
                missing = [col for col in required_columns if col not in original_fieldnames]
                print(f"Errore: Colonne mancanti: {', '.join(missing)}")
                return
            input_data = list(reader)
    except Exception as e:
        print(f"Errore lettura CSV '{input_csv_path}': {type(e).__name__}: {e}")
        return

    if row_limit is not None and row_limit > 0:
        if row_limit < len(input_data):
            print(f"INFO: Limite a {row_limit} righe (su {len(input_data)}).")
            input_data = input_data[:row_limit]
        else:
             print(f"INFO: Limite ({row_limit}) >= righe ({len(input_data)}). Processando tutte.")
    elif row_limit is not None:
         print("INFO: Limite non valido. Processando tutte le righe.")

    total_rows_to_process = len(input_data)
    if total_rows_to_process == 0:
        print("INFO: Nessuna riga da processare.")
        # Scrivi comunque l'header nel file di output se non esiste già
        # (Modificato per creare file vuoto con header se input è vuoto)
        if not os.path.exists(output_csv_path):
             output_fieldnames = original_fieldnames[:]
             if output_column_name not in output_fieldnames:
                 output_fieldnames.append(output_column_name)
             try:
                 with open(output_csv_path, 'w', newline='', encoding='utf-8') as outfile:
                    writer = csv.DictWriter(outfile, fieldnames=output_fieldnames,
                                           extrasaction='ignore', lineterminator='\n')
                    writer.writeheader()
                 print(f"File CSV di output vuoto creato con header: '{output_csv_path}'")
             except Exception as e:
                print(f"ERRORE CRITICO scrittura header CSV output vuoto '{output_csv_path}': {type(e).__name__}: {e}")
        return # Termina l'elaborazione

    print(f"Inizio elaborazione (REGEX MODE - Improved) di {total_rows_to_process} righe da '{input_csv_path}'...")
    success_count = 0
    error_count = 0

    # --- 2. Processa ogni riga ---
    for i, row in enumerate(input_data):
        # Assume la prima riga è header, quindi la riga 1 dei dati è la riga 2 nel file CSV originale
        row_num_in_original_csv = i + 2
        sol_file_path = row.get('File', '').strip()
        start_line_str = row.get('StartLine', '').strip()
        # EndLine non è usata dalla nuova logica di estrazione, ma la leggiamo
        end_line_str = row.get('EndLine', '').strip() # Non utilizzata per l'estrazione

        extracted_code = None
        status_message = "Errore non specificato"
        output_row = row.copy() # Crea copia per aggiungere/modificare colonne

        try:
            if not sol_file_path:
                status_message = f"Errore Riga {row_num_in_original_csv}: Percorso file Solidity mancante"
            elif not start_line_str:
                status_message = f"Errore Riga {row_num_in_original_csv}: StartLine mancante (essenziale)"
            else:
                try:
                    start_line = int(start_line_str)
                    if start_line <= 0:
                         status_message = f"Errore Riga {row_num_in_original_csv}: StartLine deve essere positiva ({start_line})"
                    # Verifica esistenza file SOLO se StartLine è valida
                    elif not os.path.exists(sol_file_path):
                        status_message = f"Errore File Riga {row_num_in_original_csv}: File Solidity non trovato: '{sol_file_path}'"
                    elif not os.path.isfile(sol_file_path):
                         status_message = f"Errore File Riga {row_num_in_original_csv}: Percorso non è un file: '{sol_file_path}'"
                    else:
                        # File esiste ed è un file, procedi con la lettura e l'estrazione
                        source_code = None
                        try:
                            with open(sol_file_path, 'r', encoding='utf-8') as sol_file:
                                source_code = sol_file.read()
                        except Exception as e:
                            status_message = f"Errore Lettura File Riga {row_num_in_original_csv} ('{sol_file_path}'): {type(e).__name__}: {e}"

                        if source_code is not None:
                            # --- Chiamata alla NUOVA funzione di estrazione ---
                            extracted_code, status_message_extract = find_block_regex_and_braces(
                                source_code, start_line
                            )
                            # Aggiungi info riga CSV al messaggio di errore se fallisce
                            if not status_message_extract.startswith("Success"):
                                status_message = f"Errore Estrazione Riga {row_num_in_original_csv}: {status_message_extract}"
                            else:
                                status_message = status_message_extract # Mantiene "Success..."

                except ValueError:
                    status_message = f"Errore Riga {row_num_in_original_csv}: StartLine ('{start_line_str}') non è un numero intero valido"
                except Exception as e: # Cattura altri errori durante il parsing della riga o logica iniziale
                     status_message = f"Errore Inatteso Riga {row_num_in_original_csv} (pre-estrazione): {type(e).__name__}: {e}"

        except Exception as e:
             # Errore molto generico durante l'elaborazione della riga
             status_message = f"Errore Imprevisto Riga {row_num_in_original_csv}: {type(e).__name__}: {e}"

        # --- Registra risultato e aggiorna contatori ---
        if status_message.startswith("Success"): # Accetta "Success (...)"
            output_row[output_column_name] = extracted_code if extracted_code is not None else "Success but empty code returned" # Aggiungi controllo null
            success_count += 1
        else:
            # Assicura che il messaggio di errore sia scritto anche se extracted_code fosse None
            output_row[output_column_name] = status_message
            error_count += 1
            # Stampa errore subito per debug più facile
            print(f"  [ERRORE] {status_message}")


        processed_data.append(output_row)

        # Log progresso
        current_processed = i + 1
        if current_processed % 50 == 0 or current_processed == total_rows_to_process:
             print(f"  Elaborate {current_processed}/{total_rows_to_process}... (Successi: {success_count}, Errori: {error_count})")

    print(f"Elaborazione completata. Totale Righe: {total_rows_to_process}, Successi: {success_count}, Errori: {error_count}.")
    if error_count > 0:
        print(f"ATTENZIONE: Ci sono stati {error_count} errori. Controllare '{output_csv_path}' per i dettagli.")

    # --- 4. Scrivi CSV di Output (come prima, ma con gestione fieldnames migliorata) ---
    output_fieldnames = original_fieldnames[:] # Crea una copia
    if output_column_name not in output_fieldnames:
        output_fieldnames.append(output_column_name)

    # Assicurati che la directory di output esista
    output_dir = os.path.dirname(output_csv_path)
    if output_dir and not os.path.exists(output_dir):
         try:
             os.makedirs(output_dir)
             print(f"INFO: Creata directory di output: '{output_dir}'")
         except Exception as e:
             print(f"ERRORE CRITICO: Impossibile creare directory di output '{output_dir}': {e}")
             return # Non si può scrivere il file

    print(f"Tentativo di scrittura output: '{output_csv_path}'")
    try:
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as outfile:
            # Usa extrasaction='ignore' per non fallire se la riga originale
            # avesse colonne extra non presenti in fieldnames (improbabile con DictReader ma sicuro)
            # Usa lineterminator='\n' per consistenza tra OS.
            writer = csv.DictWriter(outfile, fieldnames=output_fieldnames,
                                    extrasaction='ignore', lineterminator='\n')
            writer.writeheader()
            writer.writerows(processed_data) # Scrive tutte le righe processate (successi ed errori)
        print(f"File CSV di output scritto con successo: '{output_csv_path}'")
    except Exception as e:
        print(f"ERRORE CRITICO scrittura CSV output '{output_csv_path}': {type(e).__name__}: {e}")



def process_solidity_csv_regex_by_hash(
    input_csv_path: str,
    output_csv_path: str,
    contracts_dir: str,
    filters: Optional[Dict[str, Any]] = None,
    row_limit: Optional[int] = None
):
    """
    Processa un CSV con colonne 'Hash' e 'StartLine', cercando per ciascuna riga
    il file .sol in contracts_dir il cui NOME (basename) contiene il valore di 'Hash'.
    Quindi estrae il blocco funzione con find_block_regex_and_braces e salva il risultato
    in un nuovo CSV con colonna aggiuntiva 'ExtractedFunction'.

    Args:
        input_csv_path (str): Percorso al CSV di input.
        output_csv_path (str): Percorso al CSV di output.
        contracts_dir (str): Directory radice con i file .sol.
        filters (dict[str, Any], optional): Filtri da applicare alle righe CSV prima del processing.
        row_limit (int, optional): Se specificato, processa solo le prime row_limit righe dopo i filtri.
    """
    required_cols = ['Hash', 'StartLine']
    output_col = 'ExtractedFunctionMutation'

    # 1. Leggi e verifica CSV di input
    if not os.path.isfile(input_csv_path):
        raise FileNotFoundError(f"CSV di input non trovato: {input_csv_path}")
    with open(input_csv_path, 'r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames or []
        if not all(col in fieldnames for col in required_cols):
            missing = [col for col in required_cols if col not in fieldnames]
            raise ValueError(f"CSV mancante delle colonne: {missing}")
        rows = list(reader)

    # 2. Applica filtri (opzionale)
    if filters:
        total_before = len(rows)
        def matches(r: Dict[str, Any]) -> bool:
            for key, val in filters.items():
                cell = r.get(key)
                if isinstance(val, (list, set, tuple)):
                    if cell not in val:
                        return False
                else:
                    if cell != val:
                        return False
            return True
        rows = [r for r in rows if matches(r)]
        print(f"Filtrate righe: {len(rows)}/{total_before} (filtri={filters})")

    # 3. Applica row_limit (opzionale)
    if row_limit and row_limit > 0 and row_limit < len(rows):
        print(f"Limite righe: processerò solo le prime {row_limit}/{len(rows)} righe")
        rows = rows[:row_limit]

    total = len(rows)
    print(f"Inizio elaborazione: {total} righe da processare.")

    # 4. Indicizza tutti i file .sol in contracts_dir
    sol_files = []
    for root, _, files in os.walk(contracts_dir):
        for fn in files:
            if fn.lower().endswith('.sol'):
                sol_files.append(os.path.join(root, fn))
    print(f"Trovati {len(sol_files)} file .sol in '{contracts_dir}'.")

    processed = []

    # 5. Processa ogni riga con log di progresso
    for idx, row in enumerate(rows, start=1):
        print(f"-- Riga {idx}/{total} --")
        identifier = row['Hash'].strip()
        sl_str = row['StartLine'].strip()
        out_row = row.copy()
        result: str

        # Cerca file il cui basename contiene l'identificatore
        needle = identifier.lower()
        found_path: Optional[str] = None
        for path in sol_files:
            if needle in os.path.basename(path).lower():
                found_path = path
                print(f"  [TROVATO] file '{path}' contiene '{identifier}' nel nome.")
                break
        if not found_path:
            result = f"Errore Riga {idx+1}: nessun .sol in '{contracts_dir}' con nome contenente '{identifier}'"
            print(f"  [ERRORE] {result}")
            out_row[output_col] = result
            processed.append(out_row)
            continue

        # Verifica StartLine
        try:
            sl = int(sl_str)
            if sl <= 0:
                raise ValueError
        except ValueError:
            result = f"Errore Riga {idx+1}: StartLine non valida ('{sl_str}')"
            print(f"  [ERRORE] {result}")
            out_row[output_col] = result
            processed.append(out_row)
            continue

        # Lettura sorgente ed estrazione blocco
        try:
            with open(found_path, 'r', encoding='utf-8') as f:
                src = f.read()
            print(f"  Estraggo blocco funzione da riga {sl} in '{found_path}'...")
            extracted, status = find_block_regex_and_braces(src, sl)
            if status.startswith("Success"):
                result = extracted
                print(f"  [SUCCESS] blocco estratto con stato {status}.")
            else:
                result = f"Errore Estrazione Riga {idx+1}: {status}"
                print(f"  [ERRORE] {result}")
        except Exception as e:
            result = f"Errore Lettura/Estrazione Riga {idx+1}: {type(e).__name__}: {e}"
            print(f"  [ERRORE] {result}")

        out_row[output_col] = result
        processed.append(out_row)

    # 6. Scrittura CSV di output
    out_fields = fieldnames.copy()
    if output_col not in out_fields:
        out_fields.append(output_col)
    os.makedirs(os.path.dirname(output_csv_path) or '.', exist_ok=True)
    print(f"Scrittura CSV di output su '{output_csv_path}'...")
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=out_fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(processed)
    print(f"Elaborazione completata. Output scritto su '{output_csv_path}' ({len(processed)} righe).")



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






sumo_results = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/sumo_results.csv"
sumo_results_with_function_original = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/sumo_results_with_functions_original.csv"
sumo_results_with_function_mutation = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/sumo_results_with_functions_mutation.csv"
sumo_results_with_function_extracted = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/sumo_results_function_extracted.csv"
sumo_results_final = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/sumo_results_final.csv"
sumo_results_filtered = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/sumo_results_filtered.csv"




mutation_folder = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/mutants"
json_results = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/results.json"
json_results_filtered = "/Users/matteocicalese/PycharmProjects/SuMo-SOlidity-MUtator/sumo/results/results_filtered.json"


# process_solidity_csv_regex(sumo_results, sumo_results_with_function_original)
# process_solidity_csv_regex_by_hash(sumo_results, sumo_results_with_function_mutation, mutation_folder)
# le_operator_fix(sumo_results_with_function_mutation)

# convert_csv_to_json(sumo_results_final, json_results)




filter_csv_per_operator(sumo_results_final, "UTR", sumo_results_filtered)
convert_csv_to_json(sumo_results_filtered, json_results_filtered)


