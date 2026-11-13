"""Case 01 - Funding Forensics (Indian startup funding)."""
from __future__ import annotations

import datetime as dt
import re

from .. import clean
from ..base import Column, Dataset, Level, Table
from . import _names

VERTICALS = ["FinTech", "EdTech", "E-Commerce", "Consumer Internet", "Healthcare", "Logistics", "SaaS", "Food & Beverage"]
CITIES = ["Bangalore", "Bengaluru", "bangalore", "Bangalore / USA", "Mumbai", "New Delhi", "Delhi", "Gurgaon",
          "Gurugram", "Pune", "Hyderabad", "Chennai", "Noida", "\\\\xc2\\\\xa0Gurgaon", "Ahmedabad", "nan"]
ROUNDS = ["Seed Funding", "Seed / Angel Funding", "Seed\\\\nFunding", "Private Equity", "Series A", "Series B",
          "Pre-Series A", "Debt Funding", "Series C"]


class Funding(Dataset):
    key = "funding"
    case_no = 1
    expected_files = ("startup_funding.csv",)
    patterns = ("startup", "funding")
    columns = {
        "date": ("Date dd/mm/yyyy", "Date", "deal date", "funding date"),
        "startup": ("Startup Name", "startup", "company", "company name"),
        "vertical": ("Industry Vertical", "industry", "sector"),
        "subvertical": ("SubVertical", "sub vertical"),
        "city": ("City  Location", "City Location", "city", "location", "hq"),
        "investors": ("Investors Name", "investors", "investor"),
        "round_type": ("InvestmentnType", "Investment Type", "InvestmentType", "round", "funding round", "stage"),
        "amount": ("Amount in USD", "amount usd", "amount", "funding amount"),
    }
    required = ("date", "startup", "amount")
    source = {"name": "Indian Startup Funding (Kaggle: sudalairajkumar/indian-startup-funding)",
              "url": "https://www.kaggle.com/datasets/sudalairajkumar/indian-startup-funding", "licence": "CC0: Public Domain"}
    max_rows = 4000

    # ---------- placeholder in the original Kaggle layout ----------
    def placeholder(self):
        r = self.rng
        head = ["Sr No", "Date dd/mm/yyyy", "Startup Name", "Industry Vertical", "SubVertical", "City  Location",
                "Investors Name", "InvestmentnType", "Amount in USD", "Remarks"]
        rows, names = [], [_names.startup(r) for _ in range(260)]
        start = dt.date(2015, 1, 1)
        for i in range(1, 641):
            d = start + dt.timedelta(days=r.randrange(0, 1850))
            date = d.strftime("%d/%m/%Y")
            if r.random() < 0.01:
                date = date[:5] + "." + date[6:]          # e.g. 12/05.2015 like the real export
            amt = r.choice([0, 1, 1, 1, 2]) and int(r.lognormvariate(14.5, 1.6))
            if amt:
                s = f"{amt:,}"
                if r.random() < 0.5:                     # Indian digit grouping like 1,51,09,500
                    t = str(amt)
                    head3, rest = t[-3:], t[:-3]
                    parts = []
                    while len(rest) > 2:
                        parts.insert(0, rest[-2:])
                        rest = rest[:-2]
                    s = ",".join(([rest] if rest else []) + parts + [head3])
            else:
                s = r.choice(["N/A", "N/A", "undisclosed", "Undisclosed", "unknown"])
            inv = ", ".join(sorted({_names.fund(r) for _ in range(r.choice([1, 1, 2, 3]))}))
            rows.append([str(i), date, r.choice(names), r.choice(VERTICALS), "", r.choice(CITIES), inv,
                         r.choice(ROUNDS), s, "PLACEHOLDER SAMPLE - replace with the real dataset"])
        return head, rows

    # ---------- clean + plant ----------
    def build(self, recs):
        rounds, links = [], []
        for i, rec in enumerate(self.sample(recs), start=1):
            amount = clean.parse_number(rec.get("amount"))
            rounds.append([i, clean.parse_date(rec.get("date")), clean.fix_text(rec.get("startup")),
                           clean.fix_text(rec.get("vertical")), (rec.get("city") or "").strip() or None,
                           clean.fix_text(rec.get("investors")), clean.fix_text(rec.get("round_type")),
                           int(amount) if amount else None, (rec.get("amount") or "").strip() or None])
        dates = sorted(r[1] for r in rounds if r[1])
        self.freeze = dates[-1]
        nid = len(rounds) + 1
        # planted 1: two future-dated rounds (data entry / backdating fraud)
        pool = [r for r in rounds if r[7] and r[1]]
        donors = pool[:: max(1, len(pool) // 7)][:4]
        fz = dt.date.fromisoformat(self.freeze)
        for k, days in ((0, 43), (1, 400)):
            src = list(donors[k])
            src[0], src[1] = nid, (fz + dt.timedelta(days=days)).isoformat()
            rounds.append(src)
            self.plant("funding_rounds", nid, f"future-dated copy of round {donors[k][0]} ({src[1]}), after freeze {self.freeze}")
            nid += 1
        # planted 2: duplicate filings with different capitalisation / stray spaces
        for k, transform in ((2, lambda s: " " + s.upper()), (3, lambda s: s.lower() + " ")):
            src = list(donors[k])
            src[0], src[2] = nid, transform(src[2])
            rounds.append(src)
            self.plant("funding_rounds", nid, f"duplicate filing of round {donors[k][0]} with startup name '{src[2]}'")
            nid += 1
        for r in rounds:
            for inv in re.split(r",|&| and ", r[5] or ""):
                inv = " ".join(inv.split())
                if inv and inv.lower() not in ("undisclosed investors", "undisclosed", "others"):
                    links.append((r[0], inv))
        links = sorted(set(links))
        return [
            Table("funding_rounds", "One row per reported funding round (cleaned dates/amounts, raw city text kept on purpose).", [
                Column("round_id", "INTEGER", "Row id", "PRIMARY KEY"),
                Column("deal_date", "TEXT", "ISO date YYYY-MM-DD (parsed from messy dd/mm/yyyy text)"),
                Column("startup", "TEXT", "Startup name as filed (spacing/case not normalised)"),
                Column("vertical", "TEXT", "Industry vertical"),
                Column("city_raw", "TEXT", "City exactly as typed in the source - many spellings"),
                Column("investors", "TEXT", "Comma-separated investor list"),
                Column("round_type", "TEXT", "Round type as filed"),
                Column("amount_usd", "INTEGER", "Amount in USD; NULL when undisclosed"),
                Column("amount_raw", "TEXT", "Original amount text"),
            ], [tuple(r) for r in rounds]),
            Table("round_investors", "One row per (round, investor) - split from funding_rounds.investors.", [
                Column("round_id", "INTEGER", "Round", "REFERENCES funding_rounds(round_id)"),
                Column("investor", "TEXT", "Single investor name"),
            ], links),
        ]

    def case(self, tables):
        return {
            "title": "Funding Forensics",
            "industry": "Venture Capital",
            "tagline": "Reported rounds don't add up. Audit the startup funding ledger before the annual report ships.",
            "client": "An Indian VC research desk",
            "brief": [
                "The research desk publishes a yearly 'State of Indian Startups' report built from this funding ledger.",
                f"The ledger was frozen on {self.freeze}, yet the numbers keep shifting: some rounds are counted twice, "
                "city names come in a dozen spellings and a few entries look backdated.",
                "Before the report goes to print, prove every number with SQL.",
            ],
            "difficulty": "Beginner",
            "accent": "orange",
        }

    def levels(self, tables):
        fz = self.freeze
        return [
            Level("Time travellers",
                  f"The ledger was frozen on {fz}. List every round dated after that day. Return round_id, startup, deal_date.",
                  ["Dates are stored as ISO text (YYYY-MM-DD), so they compare correctly as strings.",
                   f"Filter with WHERE deal_date > '{fz}'.",
                   f"SELECT round_id, startup, deal_date FROM funding_rounds WHERE deal_date > '{fz}';"],
                  f"SELECT round_id, startup, deal_date FROM funding_rounds WHERE deal_date > '{fz}'",
                  ["WHERE", "comparison", "dates as text"],
                  story="A round can't happen after the books were closed. Someone typed entries from the future."),
            Level("Bengaluru by any other name",
                  "How many rounds are filed under Bengaluru, whatever the spelling? Count rows whose city_raw contains "
                  "'bangalore' or 'bengaluru' in any letter case. Return one column: rounds.",
                  ["LOWER(city_raw) makes the comparison case-insensitive.",
                   "Use LIKE '%bangalore%' OR LIKE '%bengaluru%'.",
                   "SELECT COUNT(*) AS rounds FROM funding_rounds WHERE LOWER(city_raw) LIKE '%bangalore%' OR LOWER(city_raw) LIKE '%bengaluru%';"],
                  "SELECT COUNT(*) AS rounds FROM funding_rounds WHERE LOWER(city_raw) LIKE '%bangalore%' OR LOWER(city_raw) LIKE '%bengaluru%'",
                  ["LIKE", "LOWER", "COUNT"],
                  story="The report says Mumbai beat Bengaluru. It didn't - Bengaluru was split across spellings."),
            Level("Double-booked rounds",
                  "Find rounds filed more than once: same startup (ignore case and surrounding spaces), same deal_date and same "
                  "non-NULL amount_usd. Return startup_key (LOWER(TRIM(startup))), deal_date, amount_usd, copies.",
                  ["Group by the normalised name, the date and the amount.",
                   "Keep only groups with HAVING COUNT(*) > 1, and skip NULL amounts.",
                   "SELECT LOWER(TRIM(startup)) AS startup_key, deal_date, amount_usd, COUNT(*) AS copies FROM funding_rounds "
                   "WHERE amount_usd IS NOT NULL GROUP BY 1, 2, 3 HAVING COUNT(*) > 1;"],
                  "SELECT LOWER(TRIM(startup)) AS startup_key, deal_date, amount_usd, COUNT(*) AS copies FROM funding_rounds "
                  "WHERE amount_usd IS NOT NULL GROUP BY 1, 2, 3 HAVING COUNT(*) > 1",
                  ["GROUP BY", "HAVING", "TRIM/LOWER"],
                  story="Totals are inflated. Somebody re-filed the same cheque with a slightly different name."),
            Level("Biggest cheque of each year",
                  "For every year, find the single largest disclosed round (ties: lowest round_id). "
                  "Return year (as text 'YYYY'), startup, amount_usd - sorted by year.",
                  ["strftime('%Y', deal_date) extracts the year.",
                   "ROW_NUMBER() OVER (PARTITION BY year ORDER BY amount_usd DESC, round_id) numbers rounds inside each year.",
                   "WITH r AS (SELECT strftime('%Y', deal_date) AS year, startup, amount_usd, ROW_NUMBER() OVER "
                   "(PARTITION BY strftime('%Y', deal_date) ORDER BY amount_usd DESC, round_id) AS rn FROM funding_rounds "
                   "WHERE amount_usd IS NOT NULL AND deal_date IS NOT NULL) SELECT year, startup, amount_usd FROM r WHERE rn = 1 ORDER BY year;"],
                  "WITH r AS (SELECT strftime('%Y', deal_date) AS year, startup, amount_usd, ROW_NUMBER() OVER "
                  "(PARTITION BY strftime('%Y', deal_date) ORDER BY amount_usd DESC, round_id) AS rn FROM funding_rounds "
                  "WHERE amount_usd IS NOT NULL AND deal_date IS NOT NULL) SELECT year, startup, amount_usd FROM r WHERE rn = 1 ORDER BY year",
                  ["CTE", "window functions", "ROW_NUMBER"], ordered=True,
                  story="The report's headline chart: the record round of every year."),
            Level("Who writes the most cheques?",
                  "Using round_investors, list the 5 investors that appear in the most rounds (ties: alphabetical). "
                  "Return investor, rounds - most active first.",
                  ["round_investors has one row per investor per round.",
                   "GROUP BY investor, then ORDER BY COUNT(*) DESC, investor and LIMIT 5.",
                   "SELECT investor, COUNT(*) AS rounds FROM round_investors GROUP BY investor ORDER BY rounds DESC, investor LIMIT 5;"],
                  "SELECT investor, COUNT(*) AS rounds FROM round_investors GROUP BY investor ORDER BY rounds DESC, investor LIMIT 5",
                  ["GROUP BY", "ORDER BY", "LIMIT"], ordered=True,
                  story="The desk wants a 'most active investors' table - from the linked table, not by eyeballing text."),
        ]
