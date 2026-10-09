# EVTX Forensics Analyzer

A Windows Event Log forensics tool built with Python and PyQt6. It provides a GUI workflow to preserve original `.evtx` evidence, convert event logs to XML, merge events from multiple XML files into a chronological timeline, apply filters, and export timeline data and statistics.

> **Project status:** Student / educational digital forensics project. Validate results independently before using them in a formal investigation.

## Features

### 1. Evidence preservation
- Accepts Windows Event Log (`.evtx`) files.
- Copies the selected source file into the `evidence/` directory using a timestamped filename.
- Computes a SHA-256 hash for the source and copied evidence file.
- Compares hashes to check whether the copy matches the source.
- Records preservation operations in JSON Lines (`.jsonl`) logs.

### 2. EVTX-to-XML conversion
- Converts preserved EVTX files to XML using the Python `Evtx` library when available.
- Includes a fallback path for `tools/evtx_dump.py` if the library is unavailable and that script is present.
- Removes invalid XML control characters before writing or parsing event data.
- Records conversion activity and reports event counts where available.

### 3. Timeline analysis
- Reads events from one or more XML files.
- Extracts fields including timestamp, channel, event ID, level, computer, provider, record ID, user, and event-data description.
- Merges events from multiple inputs into chronological order.
- Supports filters for event channels, event IDs, and time ranges in the analysis module.
- Exports results to CSV and writes accompanying statistics to JSON.

### 4. GUI and manual audit
The PyQt6 desktop interface includes:
- Copy EVTX, Convert to XML, Analyze Timeline, and View Timelines actions.
- Evidence and converted-XML file lists.
- Timeline filter controls for common Windows channels, event IDs, and time range.
- A statistics view showing total and matched events, channel distribution, and frequent event IDs.
- A manual audit tab for loading a generated timeline CSV, viewing it in a read-only table, searching keywords, and filtering by event ID, channel/source, provider, and date/time range.
- Worker threads for file copying, conversion, and timeline analysis to keep long-running operations off the main GUI thread.

## Workflow

```text
Select EVTX file
      |
      v
Copy to evidence/ + compare SHA-256 hashes
      |
      v
Convert evidence EVTX to XML in samples/
      |
      v
Select one or more XML files
      |
      v
Merge and analyze events
      |
      +--> timelines/<name>.csv
      +--> timelines/<name>_stats.json
      +--> logs/ operation records
```

## Requirements

- Windows (the GUI's administrator-elevation and timeline-folder-opening helpers are Windows-specific).
- Python 3.10 or newer is recommended.
- PyQt6
- python-evtx (imported as `Evtx`)

The converter can optionally use a local `tools/evtx_dump.py` fallback script if the Python EVTX library is unavailable. That fallback must be supplied separately; it is not included in the source files listed here.

## Installation

1. Install Python from [python.org](https://www.python.org/downloads/) if it is not already installed.
2. Clone the repository:

   ```bash
   git clone <REPOSITORY_URL>
   cd <REPOSITORY_DIRECTORY>
   ```

   Replace the placeholders with your repository URL and directory name.

3. (Recommended) Create and activate a virtual environment:

   **Windows PowerShell**
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **Command Prompt**
   ```bat
   py -m venv .venv
   .venv\Scripts\activate.bat
   ```

4. Install dependencies:

   ```bash
   python -m pip install --upgrade pip
   pip install PyQt6 python-evtx
   ```

## Usage

Run the GUI from the project directory:

```bash
python Main.py
```

If your entry-point filename differs, use that filename instead. The main application attempts to request administrator privileges on Windows at startup. Run only on a system where you have authorization to examine the selected logs.

### Step-by-step

1. **Copy EVTX**
   - Click **Copy EVTX** and choose an `.evtx` file.
   - The tool creates a timestamped evidence copy under `evidence/`.
   - It computes SHA-256 hashes for the source and copy and compares them.
   - Review the operation log and copy result.

2. **Convert to XML**
   - Click **Convert to XML**.
   - The application converts the EVTX files found in the evidence directory.
   - Converted files are saved under `samples/`.

3. **Select XML inputs**
   - Open **File Manager** and refresh the XML list if needed.
   - Select one or more XML files to analyze.

4. **Configure timeline filters (optional)**
   - In **Timeline Filters**, choose channels, enter comma-separated event IDs, and/or specify start and end times.
   - The analysis module supports channel, event ID, computer, and time filters; the current GUI exposes channels, event IDs, and time boundaries.

5. **Analyze Timeline**
   - Click **Analyze Timeline** and confirm.
   - The output CSV and statistics JSON are written to `timelines/`.
   - Review the Statistics tab and the operation log.

6. **Manual Audit**
   - In **Manual Audit**, load a timeline CSV created by the analyzer.
   - Search across visible fields or filter by event ID, source/channel, provider, and optional start/end date-time.
   - The table is read-only; clear filters to return to all loaded rows.

7. **View Timelines**
   - Use **View Timelines** to open the output directory on Windows.

## Output directories

The application creates its working directories next to the Python modules.

| Directory | Contents |
|---|---|
| `evidence/` | Timestamped copies of source EVTX files that pass the hash comparison |
| `samples/` | Converted XML event logs |
| `logs/` | JSON Lines operation logs for preservation and conversion |
| `timelines/` | Timeline CSV exports and matching `_stats.json` summaries |

Example output names (timestamps vary):

```text
evidence/
  Security_20261009_120000_EVIDENCE.evtx
samples/
  Security_20261009_120100.xml
logs/
  phase1_20261009_120000.jsonl
  conversion_20261009_120100.jsonl
timelines/
  timeline_20261009_120200.csv
  timeline_20261009_120200_stats.json
```

## Timeline CSV fields

The analyzer writes these columns:

| Field | Description |
|---|---|
| `Timestamp` | Event timestamp |
| `Channel` | Windows event channel, such as Security or System |
| `EventID` | Event identifier |
| `Level` | Event severity/level, mapped to a readable label where recognized |
| `Computer` | Computer name recorded in the event |
| `Provider` | Event provider name |
| `RecordID` | Event record identifier |
| `User` | User/account value extracted from available security or event-data fields |
| `Description` | A compact representation of event-data key/value pairs |

The statistics JSON includes total events scanned, matched events, channel counts, top event IDs, computer counts, and analysis completion time.

## Logging and integrity notes

- Operation logs use JSON Lines: one JSON object per line, typically with a timestamp, action, and detail.
- SHA-256 comparison helps detect differences between the source file and its preserved copy at copy time.
- A matching hash is useful integrity evidence, but it does **not** by itself establish chain of custody, prove that source evidence was authentic before acquisition, or make the tool forensically certified.
- Keep original media and evidence read-only where possible, preserve acquisition notes, and independently verify important findings.

## Limitations and cautions

- This project is an educational tool, not a certified forensic suite.
- Event parsing depends on the structure and quality of the XML generated from the EVTX source.
- Malformed or unsupported events may be skipped during conversion or analysis.
- The current XML event generator reads the XML file into memory and extracts event elements using a regular expression; very large XML files may require substantial memory.
- Timestamp parsing and malformed-data handling should be validated against representative logs.
- Administrator elevation is requested by the GUI on Windows; this does not guarantee every operation requires administrator rights.
- The fallback converter is used only if `tools/evtx_dump.py` exists and is runnable in the environment.
- Test on copies of evidence and do not rely on this tool as the sole basis for incident-response or legal conclusions.

## Troubleshooting

**`ModuleNotFoundError: No module named 'PyQt6'`**
```bash
python -m pip install PyQt6
```

**`ModuleNotFoundError: No module named 'Evtx'`**
```bash
python -m pip install python-evtx
```

**No EVTX files appear**
- Confirm the file was copied successfully.
- Refresh the Evidence Files list.
- Confirm the files have the `.evtx` extension and are in the project's `evidence/` directory.

**No XML files appear**
- Run the conversion step and refresh the XML list.
- Review the operation log for conversion errors.
- If `python-evtx` is not installed, ensure the optional fallback script exists at `tools/evtx_dump.py`.

**Timeline analysis returns few or no events**
- Verify that the selected XML files contain valid Windows event XML.
- Check that the selected filters match the source data.
- Review console output and the generated operation logs for skipped or malformed events.

**The application does not open the timeline folder**
- The folder-opening helper uses Windows Explorer. Open the `timelines/` directory manually if needed.

## Suggested repository structure

```text
project/
├── Main.py
├── cpy_files.py
├── evtx_converter.py
├── timeline_analyzer.py
├── evidence/                 # generated; do not commit real evidence
├── samples/                  # generated; do not commit sensitive logs
├── logs/                     # generated logs
├── timelines/                # generated CSV/JSON reports
├── tools/
│   └── evtx_dump.py           # optional fallback, if supplied
├── README.md
├── LICENSE
└── requirements.txt
```

The source files provided for this README are named `Main.py`, `cpy_files.py`, `evtx_converter.py`, and `timeline_analyzer.py`. Rename them to the module names shown above (or update the imports) so the imports in the application resolve correctly. The README assumes the cleaner names shown in the suggested structure.

## Security and privacy

Windows event logs can contain usernames, machine names, security identifiers, network details, and other sensitive information. Do not publish real evidence files, converted XML, timeline exports, or logs to a public repository without reviewing and sanitizing them first. Add generated evidence and output directories to `.gitignore` when appropriate.

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE) for details.
