"""Case 03 - Shelf Integrity Audit (quick-commerce product catalogue / inventory)."""
from __future__ import annotations

import statistics

from .. import clean
from ..base import Column, Dataset, Level, Table

CATS = {"Fruits & Vegetables": ["Onion", "Tomato Hybrid", "Potato", "Banana Robusta", "Coriander Leaves", "Green Chilli"],
        "Dairy, Bread & Batter": ["Toned Milk", "Paneer", "Curd Cup", "Brown Bread", "Idli Dosa Batter", "Salted Butter"],
        "Packaged Food": ["Basmati Rice", "Atta Whole Wheat", "Toor Dal", "Poha Thick", "Instant Noodles", "Peanut Butter"],
        "Beverages": ["Masala Chai", "Filter Coffee", "Coconut Water", "Mango Drink", "Lemon Soda", "Green Tea"],
        "Personal Care": ["Neem Face Wash", "Herbal Shampoo", "Coconut Hair Oil", "Toothpaste Clove", "Bathing Bar", "Sunscreen SPF 50"],
        "Cleaning Essentials": ["Dishwash Gel", "Floor Cleaner", "Detergent Powder", "Toilet Cleaner", "Garbage Bags", "Scrub Pad"]}
BRANDS = ["Desi Farm", "Ghar Ka", "Saffron Valley", "Kisan Fresh", "Urban Basket", "Shuddh", "NatureNest"]


class Catalog(Dataset):
    key = "catalog"
    case_no = 3
    expected_files = ("zepto_inventory.csv", "inventory.csv", "catalog.csv")
    patterns = ("inventory", "catalog", "catalogue", "zepto_v", "product")
    columns = {
        "category": ("Category",),
        "name": ("name", "product", "product name", "title"),
        "mrp": ("mrp", "max retail price", "Price_original", "original price"),
        "discount_pct": ("discountPercent", "discount percent", "discount %", "discount"),
        "available_qty": ("availableQuantity", "available quantity", "stock", "stock qty", "inventory"),
        "selling_price": ("discountedSellingPrice", "selling price", "sale price", "Price_discount", "price"),
        "weight_g": ("weightInGms", "weight", "weight in gms", "grams"),
        "out_of_stock": ("outOfStock", "out of stock", "oos"),
        "pack_qty": ("quantity", "pack quantity", "pack size", "units"),
    }
    required = ("name", "mrp", "selling_price")
    source = {"name": "Zepto Inventory Dataset (Kaggle: palvinder2006/zepto-inventory-dataset) or any catalogue export with the same columns",
              "url": "https://www.kaggle.com/datasets/palvinder2006/zepto-inventory-dataset", "licence": "MIT"}
    max_rows = 5000

    def placeholder(self):
        r = self.rng
        head = ["Category", "name", "mrp", "discountPercent", "availableQuantity", "discountedSellingPrice",
                "weightInGms", "outOfStock", "quantity"]
        rows = []
        for cat, items in CATS.items():
            for item in items:
                for brand in r.sample(BRANDS, 4):
                    for w in r.sample([100, 200, 250, 500, 1000], 2):
                        mrp = r.randint(20, 600) * 100              # paise, like the Zepto export
                        disc = r.choice([0, 5, 8, 10, 12, 15, 20, 25])
                        sp = round(mrp * (100 - disc) / 100 / 100) * 100
                        qty = r.choice([0, 0, 1, 2, 3, 5, 6, 8, 10])
                        rows.append([cat, f"{brand} {item}", str(mrp), str(disc), str(qty), str(sp), str(w),
                                     "TRUE" if qty == 0 else "FALSE", "1"])
                        if r.random() < 0.08:                      # same product listed again at another price
                            sp2 = sp + r.choice([-300, 200, 500])
                            rows.append([cat, f"{brand} {item}", str(mrp), str(disc), str(qty), str(max(sp2, 100)), str(w),
                                         "TRUE" if qty == 0 else "FALSE", "1"])
        return head, rows

    def build(self, recs):
        items = []
        for rec in self.sample(recs):
            items.append([clean.fix_text(rec.get("category")) or "Uncategorised", clean.fix_text(rec.get("name")),
                          clean.parse_number(rec.get("mrp")), clean.parse_number(rec.get("discount_pct")),
                          clean.parse_int(rec.get("available_qty")), clean.parse_number(rec.get("selling_price")),
                          clean.parse_int(rec.get("weight_g")), clean.parse_bool(rec.get("out_of_stock")),
                          clean.parse_int(rec.get("pack_qty"))])
        items = [i for i in items if i[1] and i[2] is not None and i[5] is not None]
        # Zepto-style exports store prices in paise; convert when the median MRP is implausibly high
        self.paise = statistics.median(i[2] for i in items) > 1500
        for i in items:
            if self.paise:
                i[2], i[5] = round(i[2] / 100, 2), round(i[5] / 100, 2)
            if i[3] is None and i[2]:
                i[3] = round(100 * (1 - i[5] / i[2]))
            if i[7] is None and i[4] is not None:
                i[7] = 1 if i[4] == 0 else 0
        rows = [(n + 1, *i) for n, i in enumerate(items)]
        rows = [list(r) for r in rows]
        nxt = len(rows) + 1
        # planted 1: 'ghost stock' - flagged out of stock but units on hand
        for k in range(3):
            src = list(rows[(k + 1) * len(rows) // 5])
            src[0], src[5], src[8] = nxt, 7 + k * 5, 1
            rows.append(src)
            self.plant("products", nxt, f"out_of_stock=1 but available_qty={src[5]}")
            nxt += 1
        # planted 2: discount math tampered (selling price far above what the discount implies)
        for k in range(3):
            src = list(rows[(2 * k + 1) * len(rows) // 7])
            src[0] = nxt
            src[4] = 30.0
            src[6] = round(src[3] * 0.95, 2)
            rows.append(src)
            self.plant("products", nxt, f"discount_pct=30 but selling_price={src[6]} on mrp {src[3]}")
            nxt += 1
        cats = sorted({r[1] for r in rows})
        return [
            Table("products", "Product listings in the dark-store catalogue (prices in INR).", [
                Column("sku_id", "INTEGER", "Listing id", "PRIMARY KEY"),
                Column("category", "TEXT", "Category", "REFERENCES categories(category)"),
                Column("name", "TEXT", "Product name"),
                Column("mrp", "REAL", "Maximum retail price, INR"),
                Column("discount_pct", "REAL", "Advertised discount %"),
                Column("available_qty", "INTEGER", "Units on hand"),
                Column("selling_price", "REAL", "Price charged, INR"),
                Column("weight_g", "INTEGER", "Pack weight in grams"),
                Column("out_of_stock", "INTEGER", "1 if shown as out of stock"),
                Column("pack_qty", "INTEGER", "Units per pack"),
            ], [tuple(r) for r in rows]),
            Table("categories", "Category master.", [
                Column("category", "TEXT", "Category name", "PRIMARY KEY"),
                Column("aisle_no", "INTEGER", "Aisle in the dark store"),
            ], [(c, i + 1) for i, c in enumerate(cats)]),
        ]

    def case(self, tables):
        unit = " Prices were converted from paise to rupees during cleaning." if self.paise else ""
        return {
            "title": "Shelf Integrity Audit",
            "industry": "Quick Commerce",
            "tagline": "Out-of-stock items with stock, discounts that aren't. Clean the shelf before customers notice.",
            "client": "Category management at a 10-minute grocery app",
            "brief": [
                "Customers complain: 'It said out of stock, my neighbour got it' and 'the 30% off wasn't 30% off'.",
                "You have the full product catalogue of one dark store - prices, advertised discounts and units on hand." + unit,
                "Find the listings that lie, then size the stock value per category.",
            ],
            "difficulty": "Intermediate",
            "accent": "cyan",
        }

    def levels(self, tables):
        return [
            Level("Ghost stock",
                  "List products marked out_of_stock = 1 that still have available_qty > 0. Return sku_id, name, available_qty.",
                  ["Two conditions joined with AND.",
                   "WHERE out_of_stock = 1 AND available_qty > 0",
                   "SELECT sku_id, name, available_qty FROM products WHERE out_of_stock = 1 AND available_qty > 0;"],
                  "SELECT sku_id, name, available_qty FROM products WHERE out_of_stock = 1 AND available_qty > 0",
                  ["WHERE", "AND"], story="Sales are lost on items that are sitting on the shelf."),
            Level("Discounts that don't add up",
                  "Find products where selling_price differs from mrp * (100 - discount_pct) / 100 by more than 2 rupees. "
                  "Return sku_id, mrp, discount_pct, selling_price.",
                  ["Compute the expected price from mrp and discount_pct.",
                   "ABS(actual - expected) > 2",
                   "SELECT sku_id, mrp, discount_pct, selling_price FROM products WHERE ABS(selling_price - mrp * (100 - discount_pct) / 100.0) > 2;"],
                  "SELECT sku_id, mrp, discount_pct, selling_price FROM products WHERE ABS(selling_price - mrp * (100 - discount_pct) / 100.0) > 2",
                  ["arithmetic", "ABS"], story="An advertised discount is a promise. Check the maths."),
            Level("Stock value by aisle",
                  "For in-stock products (out_of_stock = 0), compute stock value = selling_price * available_qty per category. "
                  "Return aisle_no, category, stock_value (2 decimals) - highest value first.",
                  ["JOIN products to categories to get aisle_no.",
                   "SUM(selling_price * available_qty) per category.",
                   "SELECT c.aisle_no, p.category, ROUND(SUM(p.selling_price * p.available_qty), 2) AS stock_value FROM products p "
                   "JOIN categories c ON c.category = p.category WHERE p.out_of_stock = 0 GROUP BY c.aisle_no, p.category ORDER BY stock_value DESC;"],
                  "SELECT c.aisle_no, p.category, ROUND(SUM(p.selling_price * p.available_qty), 2) AS stock_value FROM products p "
                  "JOIN categories c ON c.category = p.category WHERE p.out_of_stock = 0 GROUP BY c.aisle_no, p.category ORDER BY stock_value DESC, c.aisle_no",
                  ["JOIN", "SUM", "GROUP BY"], ordered=True, story="Finance needs the money sitting in every aisle."),
            Level("Same product, two prices",
                  "Find products listed more than once in the same category with the same name and weight but different selling prices. "
                  "Return category, name, weight_g, min_price, max_price.",
                  ["Group by category, name and weight_g.",
                   "HAVING COUNT(DISTINCT selling_price) > 1",
                   "SELECT category, name, weight_g, MIN(selling_price) AS min_price, MAX(selling_price) AS max_price FROM products "
                   "GROUP BY category, name, weight_g HAVING COUNT(DISTINCT selling_price) > 1;"],
                  "SELECT category, name, weight_g, MIN(selling_price) AS min_price, MAX(selling_price) AS max_price FROM products "
                  "GROUP BY category, name, weight_g HAVING COUNT(DISTINCT selling_price) > 1",
                  ["GROUP BY", "COUNT DISTINCT", "HAVING"], story="Two listings, one product, two prices: someone pays more."),
        ]
