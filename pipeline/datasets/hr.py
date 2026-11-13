"""Case 05 - Payroll Leak (HR employee data + derived monthly payroll)."""
from __future__ import annotations

import datetime as dt

from .. import clean
from ..base import Column, Dataset, Level, Table

DEPTS = ["Research & Development", "Sales", "Human Resources"]
ROLES = {"Research & Development": ["Research Scientist", "Laboratory Technician", "Manager", "Research Director"],
         "Sales": ["Sales Executive", "Sales Representative", "Manager"],
         "Human Resources": ["Human Resources", "Manager"]}
MONTHS = ["2021-07", "2021-08", "2021-09", "2021-10", "2021-11", "2021-12"]


class Payroll(Dataset):
    key = "payroll"
    case_no = 5
    expected_files = ("hr_employees.csv", "hr_attrition.csv")
    patterns = ("hr", "attrition", "employee", "payroll")
    columns = {
        "emp_id": ("EmployeeNumber", "employee id", "emp id", "employee_id"),
        "age": ("Age",),
        "department": ("Department", "dept"),
        "job_role": ("JobRole", "job role", "designation", "role"),
        "job_level": ("JobLevel", "job level", "grade"),
        "monthly_income": ("MonthlyIncome", "monthly income", "salary", "monthly salary"),
        "overtime": ("OverTime", "overtime"),
        "hire_date": ("Date_of_Hire", "date of hire", "hire date", "joining date", "doj"),
        "term_date": ("Date_of_termination", "date of termination", "termination date", "exit date"),
        "attrition": ("Attrition",),
    }
    required = ("department", "monthly_income")
    source = {"name": "HR Attrition data based on IBM attrition (Kaggle: singhnproud77/hr-attrition-dataset; IBM's fictional sample) or any HR export with the same columns",
              "url": "https://www.kaggle.com/datasets/singhnproud77/hr-attrition-dataset", "licence": "CC0: Public Domain"}
    max_rows = 2000

    def placeholder(self):
        r = self.rng
        head = ["Age", "Attrition", "Department", "JobLevel", "JobRole", "MonthlyIncome", "OverTime", "Date_of_Hire", "Date_of_termination"]
        rows = []
        for _ in range(420):
            d = r.choice(DEPTS)
            lvl = r.randint(1, 5)
            hire = dt.date(2016, 1, 1) + dt.timedelta(days=r.randrange(0, 1900))
            left = r.random() < 0.16
            term = (dt.date(2021, 6, 1) + dt.timedelta(days=r.randrange(0, 200))) if left else None
            rows.append([str(r.randint(21, 59)), "Yes" if left else "No", d, str(lvl), r.choice(ROLES[d]),
                         str(lvl * 2600 + r.randint(800, 3000)), r.choice(["Yes", "No", "No"]),
                         hire.strftime("%d-%m-%Y"), term.strftime("%d-%m-%Y") if term else ""])
        return head, rows

    def build(self, recs):
        emps = []
        for n, rec in enumerate(self.sample(recs), start=1):
            inc = clean.parse_number(rec.get("monthly_income"))
            if inc is None:
                continue
            emps.append([1000 + n, clean.parse_int(rec.get("age")), clean.fix_text(rec.get("department")) or "Unknown",
                         clean.fix_text(rec.get("job_role")), clean.parse_int(rec.get("job_level")), int(inc),
                         clean.parse_bool(rec.get("overtime")) or 0, clean.parse_date(rec.get("hire_date")),
                         clean.parse_date(rec.get("term_date"))])
        # synthetic bank accounts (one per employee) - case-specific, never from the source data
        for e in emps:
            e.append(f"XXXX{self.rng.randrange(10**7, 10**8)}")
        # planted 1: three accounts receiving salaries for two employees each (ghost employees)
        for k in range(3):
            a, b = emps[(k + 1) * len(emps) // 7], emps[(k + 4) * len(emps) // 9]
            b[9] = a[9]
            self.plant("employees", b[0], f"bank account {a[9]} shared with employee {a[0]}")
        # derived payroll: one payment per active month (salary + overtime top-up), deterministic
        pays, pid = [], 1
        for e in emps:
            for m in MONTHS:
                start = f"{m}-01"
                if e[7] and e[7] > f"{m}-28":
                    continue
                if e[8] and e[8] < start:
                    continue
                net = round(e[5] * 0.88 + (0.05 * e[5] if e[6] else 0), 2)
                pays.append([pid, e[0], m, net, f"{m}-28"])
                pid += 1
        # planted 2: salary kept flowing after the exit date
        leavers = [e for e in emps if e[8] and e[8] < "2021-10-01"][:4]
        if len(leavers) < 2:                      # source has no usable exit dates: mark a few leavers ourselves
            for e in emps[5:9]:
                e[8] = "2021-09-15"
                self.plant("employees", e[0], "exit_date set to 2021-09-15 by the case builder")
            leavers = emps[5:9]
            pays = [p for p in pays if not (p[1] in {e[0] for e in leavers} and p[2] > "2021-09")]
        for e in leavers:
            for m in MONTHS[-2:]:
                pays.append([pid, e[0], m, round(e[5] * 0.88, 2), f"{m}-28"])
                self.plant("payroll", pid, f"salary for {m} paid to employee {e[0]} who left on {e[8]}")
                pid += 1
        # planted 3: one-off inflated payments
        for k in range(3):
            p = pays[(k + 2) * len(pays) // 6]
            p[3] = round(p[3] * 2.4, 2)
            self.plant("payroll", p[0], "net pay inflated 2.4x for one month")
        depts = sorted({e[2] for e in emps})
        return [
            Table("departments", "Department master.", [
                Column("department", "TEXT", "Department", "PRIMARY KEY"),
                Column("cost_centre", "TEXT", "Cost centre code"),
            ], [(d, f"CC-{100 + i}") for i, d in enumerate(depts)]),
            Table("employees", "Employee master (source HR data + a synthetic bank account per employee).", [
                Column("emp_id", "INTEGER", "Employee id", "PRIMARY KEY"),
                Column("age", "INTEGER", "Age"),
                Column("department", "TEXT", "Department", "REFERENCES departments(department)"),
                Column("job_role", "TEXT", "Job role"),
                Column("job_level", "INTEGER", "Job level 1-5"),
                Column("monthly_income", "INTEGER", "Contracted gross monthly income"),
                Column("overtime", "INTEGER", "1 if eligible for overtime"),
                Column("hire_date", "TEXT", "Hire date YYYY-MM-DD"),
                Column("exit_date", "TEXT", "Exit date, NULL if still employed"),
                Column("bank_account", "TEXT", "Masked salary account"),
            ], [tuple(e) for e in emps]),
            Table("payroll", "Monthly salary payments (derived from monthly_income for this case).", [
                Column("pay_id", "INTEGER", "Payment id", "PRIMARY KEY"),
                Column("emp_id", "INTEGER", "Employee paid", "REFERENCES employees(emp_id)"),
                Column("pay_month", "TEXT", "Month 'YYYY-MM'"),
                Column("net_pay", "REAL", "Amount transferred"),
                Column("paid_on", "TEXT", "Transfer date"),
            ], [tuple(p) for p in pays]),
        ]

    def case(self, tables):
        return {
            "title": "Payroll Leak",
            "industry": "HR & Payroll",
            "tagline": "Salaries to people who left, two employees on one bank account. Plug the payroll leak.",
            "client": "Internal audit, mid-size company",
            "brief": [
                "Payroll costs rose this half-year while headcount fell. The CFO asked internal audit to look.",
                "You have the employee master, the department list and every salary transfer from July to December 2021.",
                "Find money that should never have left the account - and who received it.",
            ],
            "difficulty": "Advanced",
            "accent": "orange",
        }

    def levels(self, tables):
        return [
            Level("Paid after leaving",
                  "List salary payments for a month that starts after the employee's exit_date. Return pay_id, emp_id, pay_month.",
                  ["JOIN payroll to employees.",
                   "A month 'YYYY-MM' starts on pay_month || '-01'. Compare that with exit_date.",
                   "SELECT p.pay_id, p.emp_id, p.pay_month FROM payroll p JOIN employees e ON e.emp_id = p.emp_id "
                   "WHERE e.exit_date IS NOT NULL AND p.pay_month || '-01' > e.exit_date;"],
                  "SELECT p.pay_id, p.emp_id, p.pay_month FROM payroll p JOIN employees e ON e.emp_id = p.emp_id "
                  "WHERE e.exit_date IS NOT NULL AND p.pay_month || '-01' > e.exit_date",
                  ["JOIN", "string concatenation", "dates"], story="Once someone leaves, the salary stops. Unless it doesn't."),
            Level("One account, two salaries",
                  "Find bank accounts that receive salary for more than one employee. Return bank_account, employees.",
                  ["Group the employee master by bank_account.",
                   "HAVING COUNT(*) > 1",
                   "SELECT bank_account, COUNT(*) AS employees FROM employees GROUP BY bank_account HAVING COUNT(*) > 1;"],
                  "SELECT bank_account, COUNT(*) AS employees FROM employees GROUP BY bank_account HAVING COUNT(*) > 1",
                  ["GROUP BY", "HAVING"], story="Classic ghost-employee pattern: a fake hire paid into a real person's account."),
            Level("The 2x payslip",
                  "Find payments where net_pay is more than 1.5 times the employee's monthly_income. "
                  "Return pay_id, emp_id, net_pay, monthly_income.",
                  ["JOIN to employees to get monthly_income.",
                   "WHERE p.net_pay > 1.5 * e.monthly_income",
                   "SELECT p.pay_id, p.emp_id, p.net_pay, e.monthly_income FROM payroll p JOIN employees e ON e.emp_id = p.emp_id "
                   "WHERE p.net_pay > 1.5 * e.monthly_income;"],
                  "SELECT p.pay_id, p.emp_id, p.net_pay, e.monthly_income FROM payroll p JOIN employees e ON e.emp_id = p.emp_id "
                  "WHERE p.net_pay > 1.5 * e.monthly_income",
                  ["JOIN", "comparison"], story="Bonuses go through a different system. A payslip should never double."),
            Level("Leak league table",
                  "Rank departments by money paid after exit (the payments from level 1). Return department, cost_centre, "
                  "leaked (2 decimals), leak_rank (RANK, 1 = biggest) - sorted by leak_rank, ties by department.",
                  ["Reuse the level-1 filter and SUM(net_pay) per department.",
                   "RANK() OVER (ORDER BY SUM(p.net_pay) DESC) works directly in a grouped query.",
                   "SELECT e.department, d.cost_centre, ROUND(SUM(p.net_pay), 2) AS leaked, RANK() OVER (ORDER BY SUM(p.net_pay) DESC) AS leak_rank "
                   "FROM payroll p JOIN employees e ON e.emp_id = p.emp_id JOIN departments d ON d.department = e.department "
                   "WHERE e.exit_date IS NOT NULL AND p.pay_month || '-01' > e.exit_date GROUP BY e.department, d.cost_centre ORDER BY leak_rank;"],
                  "SELECT e.department, d.cost_centre, ROUND(SUM(p.net_pay), 2) AS leaked, RANK() OVER (ORDER BY SUM(p.net_pay) DESC) AS leak_rank "
                  "FROM payroll p JOIN employees e ON e.emp_id = p.emp_id JOIN departments d ON d.department = e.department "
                  "WHERE e.exit_date IS NOT NULL AND p.pay_month || '-01' > e.exit_date GROUP BY e.department, d.cost_centre ORDER BY leak_rank, e.department",
                  ["3-table JOIN", "RANK", "window over aggregate"], ordered=True, story="The CFO wants to know which department to talk to first."),
        ]
