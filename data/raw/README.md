# data/raw

Put your source CSV or XLSX files here, then run:

    python -m pipeline.build

Suggested names: `startup_funding.csv`, `quick_commerce.csv`, `zepto_inventory.csv`, `upi_transactions.csv`, `hr_employees.csv`.
Any name works as long as the headers match; see `docs/DATA-INPUTS.md` for the accepted headers per case.

Files in this folder are ignored by git on purpose (they can be large and carry their own licences).
Only the processed `data/db/*.sqlite`, `data/cases.json` and `data/schemas/*.sql` are committed.
