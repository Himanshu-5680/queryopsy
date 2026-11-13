"""Case 04 - UPI Fraud Desk (UPI transaction log)."""
from __future__ import annotations

import datetime as dt

from .. import clean
from ..base import Column, Dataset, Level, Table

TYPES = ["P2P", "P2M", "Bill Payment", "Recharge"]
MCAT = ["Grocery", "Food", "Shopping", "Fuel", "Entertainment", "Utilities", "Transport", "Healthcare", "Education", "Other"]
BANKS = ["SBI", "HDFC", "ICICI", "Axis", "Kotak", "PNB", "Yes Bank", "IndusInd"]
STATES = ["Maharashtra", "Karnataka", "Delhi", "Uttar Pradesh", "Tamil Nadu", "Telangana", "Gujarat", "West Bengal", "Rajasthan"]
AGES = ["18-25", "26-35", "36-45", "46-55", "56+"]


class Upi(Dataset):
    key = "upi"
    case_no = 4
    expected_files = ("upi_transactions.csv", "upi_transactions_2024.csv")
    patterns = ("upi", "transaction", "payment")
    columns = {
        "txn_id": ("transaction id", "transaction_id", "txn id", "id"),
        "ts": ("timestamp", "datetime", "date time", "txn time", "date"),
        "txn_type": ("transaction type", "type"),
        "merchant_category": ("merchant_category", "category"),
        "amount": ("amount (INR)", "amount", "amount inr", "value"),
        "status": ("transaction_status", "status"),
        "sender_age": ("sender_age_group", "age group"),
        "sender_state": ("sender_state", "state"),
        "sender_bank": ("sender_bank", "payer bank", "from bank"),
        "receiver_bank": ("receiver_bank", "payee bank", "to bank"),
        "device": ("device_type", "device"),
        "network": ("network_type", "network"),
        "fraud_flag": ("fraud_flag", "is_fraud", "fraud", "label"),
    }
    required = ("ts", "amount", "sender_bank", "receiver_bank", "fraud_flag")
    source = {"name": "UPI Transactions 2024 (Kaggle: skullagos5246/upi-transactions-2024-dataset; simulated by its author) or any export with the same columns",
              "url": "https://www.kaggle.com/datasets/skullagos5246/upi-transactions-2024-dataset", "licence": "CC0: Public Domain"}
    max_rows = 7000

    def placeholder(self):
        r = self.rng
        head = ["transaction id", "timestamp", "transaction type", "merchant_category", "amount (INR)", "transaction_status",
                "sender_age_group", "receiver_age_group", "sender_state", "sender_bank", "receiver_bank", "device_type",
                "network_type", "fraud_flag", "hour_of_day", "day_of_week", "is_weekend"]
        rows = []
        t0 = dt.datetime(2024, 1, 1)
        for i in range(3000):
            ts = t0 + dt.timedelta(seconds=r.randrange(0, 366 * 86400))
            hour = ts.hour
            fraud = 1 if r.random() < (0.012 if 6 <= hour <= 22 else 0.04) else 0
            amt = int(r.lognormvariate(6.6, 1.1)) + 10
            rows.append([f"TXN{i + 1:010d}", ts.strftime("%Y-%m-%d %H:%M:%S"), r.choice(TYPES), r.choice(MCAT), str(amt),
                         "FAILED" if r.random() < 0.05 else "SUCCESS", r.choice(AGES), r.choice(AGES), r.choice(STATES),
                         r.choice(BANKS), r.choice(BANKS), r.choice(["Android", "Android", "iOS", "Web"]),
                         r.choice(["4G", "4G", "5G", "WiFi", "3G"]), str(fraud), str(hour), ts.strftime("%A"),
                         "1" if ts.weekday() >= 5 else "0"])
        return head, rows

    def build(self, recs):
        txns = []
        for n, rec in enumerate(self.sample(recs), start=1):
            ts = clean.parse_datetime(rec.get("ts"))
            amt = clean.parse_number(rec.get("amount"))
            if ts is None or amt is None:
                continue
            txns.append([clean.fix_text(rec.get("txn_id")) or f"T{n:08d}", ts, clean.fix_text(rec.get("txn_type")),
                         clean.fix_text(rec.get("merchant_category")), round(amt, 2),
                         (clean.fix_text(rec.get("status")) or "SUCCESS").upper(), clean.fix_text(rec.get("sender_age")),
                         clean.fix_text(rec.get("sender_state")), clean.fix_text(rec.get("sender_bank")),
                         clean.fix_text(rec.get("receiver_bank")), clean.fix_text(rec.get("device")),
                         clean.fix_text(rec.get("network")), clean.parse_bool(rec.get("fraud_flag")) or 0])
        # planted: unflagged 'midnight whales' - large successful transfers between 00:00 and 04:59
        for k in range(4):
            src = list(txns[(k + 1) * len(txns) // 5])
            day = src[1][:10]
            src[0] = f"PLANT{k + 1:05d}"
            src[1] = f"{day} 0{k + 1}:1{k}:0{k}"
            src[4] = 95000.0 + 12500 * k
            src[5], src[12], src[2] = "SUCCESS", 0, "P2P"
            txns.append(src)
            self.plant("transactions", src[0], f"unflagged INR {src[4]:.0f} P2P transfer at {src[1][11:]}")
        banks = sorted({t[8] for t in txns if t[8]} | {t[9] for t in txns if t[9]})
        return [
            Table("transactions", "UPI transactions with the fraud model's label (fraud_flag).", [
                Column("txn_id", "TEXT", "Transaction id", "PRIMARY KEY"),
                Column("ts", "TEXT", "Timestamp 'YYYY-MM-DD HH:MM:SS'"),
                Column("txn_type", "TEXT", "P2P, P2M, Bill Payment, Recharge"),
                Column("merchant_category", "TEXT", "Merchant category"),
                Column("amount", "REAL", "Amount in INR"),
                Column("status", "TEXT", "SUCCESS / FAILED"),
                Column("sender_age", "TEXT", "Sender age band"),
                Column("sender_state", "TEXT", "Sender state"),
                Column("sender_bank", "TEXT", "Payer bank", "REFERENCES banks(bank)"),
                Column("receiver_bank", "TEXT", "Payee bank", "REFERENCES banks(bank)"),
                Column("device", "TEXT", "Device type"),
                Column("network", "TEXT", "Network type"),
                Column("fraud_flag", "INTEGER", "1 = flagged as fraud by the model"),
            ], [tuple(t) for t in txns]),
            Table("banks", "Bank master.", [
                Column("bank", "TEXT", "Bank short name", "PRIMARY KEY"),
                Column("is_private", "INTEGER", "1 for private-sector banks"),
            ], [(b, 0 if b in ("SBI", "PNB", "Bank of Baroda", "Canara", "Union Bank") else 1) for b in banks]),
        ]

    def case(self, tables):
        return {
            "title": "UPI Fraud Desk",
            "industry": "FinTech / Payments",
            "tagline": "The fraud model flags thousands of payments. Find where it's blind before the RBI audit does.",
            "client": "Risk team of a payments app",
            "brief": [
                "Your payments app routes millions of UPI transfers. A machine-learning model labels each one (fraud_flag).",
                "The regulator's audit is next month. You must explain when fraud happens, which bank corridors leak "
                "the most money, and which big transfers slipped through without a flag.",
            ],
            "difficulty": "Advanced",
            "accent": "lime",
        }

    def levels(self, tables):
        return [
            Level("The riskiest hour",
                  "Which hour of the day (0-23) has the highest fraud rate among hours with at least 50 transactions? "
                  "Return hour (integer), txns, fraud_rate_pct (2 decimals). One row.",
                  ["CAST(strftime('%H', ts) AS INTEGER) gives the hour.",
                   "AVG(fraud_flag) * 100 is the rate. HAVING COUNT(*) >= 50, ORDER BY rate DESC LIMIT 1.",
                   "SELECT CAST(strftime('%H', ts) AS INTEGER) AS hour, COUNT(*) AS txns, ROUND(100.0 * AVG(fraud_flag), 2) AS fraud_rate_pct "
                   "FROM transactions GROUP BY hour HAVING COUNT(*) >= 50 ORDER BY fraud_rate_pct DESC, hour LIMIT 1;"],
                  "SELECT CAST(strftime('%H', ts) AS INTEGER) AS hour, COUNT(*) AS txns, ROUND(100.0 * AVG(fraud_flag), 2) AS fraud_rate_pct "
                  "FROM transactions GROUP BY hour HAVING COUNT(*) >= 50 ORDER BY AVG(fraud_flag) DESC, hour LIMIT 1",
                  ["strftime", "GROUP BY", "HAVING"], story="Fraudsters keep office hours too. Find theirs."),
            Level("Leakiest corridors",
                  "Top 3 sender_bank -> receiver_bank pairs by total amount of fraud-flagged transactions. "
                  "Return sender_bank, receiver_bank, fraud_amount (2 decimals) - largest first.",
                  ["Filter fraud_flag = 1 first.",
                   "GROUP BY both bank columns, ORDER BY the sum DESC, LIMIT 3.",
                   "SELECT sender_bank, receiver_bank, ROUND(SUM(amount), 2) AS fraud_amount FROM transactions WHERE fraud_flag = 1 "
                   "GROUP BY sender_bank, receiver_bank ORDER BY fraud_amount DESC LIMIT 3;"],
                  "SELECT sender_bank, receiver_bank, ROUND(SUM(amount), 2) AS fraud_amount FROM transactions WHERE fraud_flag = 1 "
                  "GROUP BY sender_bank, receiver_bank ORDER BY SUM(amount) DESC, sender_bank, receiver_bank LIMIT 3",
                  ["GROUP BY two columns", "ORDER BY", "LIMIT"], ordered=True, story="Money moves along corridors. Follow it."),
            Level("Midnight whales",
                  "List successful transfers above INR 50,000 made between 00:00 and 04:59 that were NOT flagged. "
                  "Return txn_id, ts, amount.",
                  ["Hour 00-04 means strftime('%H', ts) < '05'.",
                   "Combine status = 'SUCCESS', fraud_flag = 0, amount > 50000.",
                   "SELECT txn_id, ts, amount FROM transactions WHERE status = 'SUCCESS' AND fraud_flag = 0 AND amount > 50000 "
                   "AND strftime('%H', ts) < '05';"],
                  "SELECT txn_id, ts, amount FROM transactions WHERE status = 'SUCCESS' AND fraud_flag = 0 AND amount > 50000 "
                  "AND strftime('%H', ts) < '05'",
                  ["WHERE", "strftime", "AND"], story="The model watches small, noisy payments. Who watches the big quiet ones?"),
            Level("Public vs private banks",
                  "Compare fraud rates for senders from public-sector and private banks. Return bank_type ('private' or 'public'), "
                  "txns, fraud_rate_pct (2 decimals).",
                  ["JOIN transactions to banks on sender_bank = bank.",
                   "CASE WHEN b.is_private = 1 THEN 'private' ELSE 'public' END",
                   "SELECT CASE WHEN b.is_private = 1 THEN 'private' ELSE 'public' END AS bank_type, COUNT(*) AS txns, "
                   "ROUND(100.0 * AVG(t.fraud_flag), 2) AS fraud_rate_pct FROM transactions t JOIN banks b ON b.bank = t.sender_bank GROUP BY bank_type;"],
                  "SELECT CASE WHEN b.is_private = 1 THEN 'private' ELSE 'public' END AS bank_type, COUNT(*) AS txns, "
                  "ROUND(100.0 * AVG(t.fraud_flag), 2) AS fraud_rate_pct FROM transactions t JOIN banks b ON b.bank = t.sender_bank GROUP BY bank_type",
                  ["JOIN", "CASE WHEN", "AVG"], story="The audit committee wants one table for the slide deck."),
        ]
