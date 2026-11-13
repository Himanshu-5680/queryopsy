"""Case 02 - Dark Store Delivery Audit (quick-commerce orders)."""
from __future__ import annotations

from .. import clean
from ..base import Column, Dataset, Level, Table

PLATFORMS = {"Blinkit": 10, "Zepto": 10, "Swiggy Instamart": 15, "BigBasket Now": 20, "Flipkart Minutes": 12, "JioMart Express": 25}
CITIES = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Pune", "Chennai", "Kolkata", "Noida", "Gurugram", "Jaipur"]
CATS = ["Dairy", "Snacks", "Fruits & Vegetables", "Personal Care", "Beverages", "Bakery", "Household", "Baby Care"]
PAY = ["UPI", "Card", "Wallet", "Cash on Delivery"]


class QuickCommerce(Dataset):
    key = "quickcommerce"
    case_no = 2
    expected_files = ("quick_commerce.csv", "quick_commerce_data.csv")
    patterns = ("quick", "commerce", "qcommerce", "q_commerce", "instamart", "blinkit")
    columns = {
        "order_id": ("Order_ID", "order id", "orderid"),
        "platform": ("Company", "platform", "app", "brand"),
        "city": ("City",),
        "order_value": ("Order_Value", "order value", "order amount", "amount", "total"),
        "delivery_min": ("Delivery_Time_Min", "delivery time", "delivery minutes", "delivery_time"),
        "distance_km": ("Distance_Km", "distance"),
        "items": ("Items_Count", "items", "item count", "quantity"),
        "category": ("Product_Category", "category"),
        "payment": ("Payment_Method", "payment", "payment mode"),
        "customer_rating": ("Customer_Rating", "rating"),
        "discount": ("Discount_Applied", "discount"),
        "partner_rating": ("Delivery_Partner_Rating", "partner rating", "rider rating"),
    }
    required = ("order_id", "platform", "city", "delivery_min", "distance_km")
    source = {"name": "Quick Commerce Dataset (Kaggle: rohitgrewal/quick-commerce-dataset) or any orders export with the same columns",
              "url": "https://www.kaggle.com/datasets/rohitgrewal/quick-commerce-dataset", "licence": "ODbL (check the copy you use)"}
    max_rows = 6000

    def placeholder(self):
        r = self.rng
        head = ["Order_ID", "Company", "City", "Customer_Age", "Order_Value", "Delivery_Time_Min", "Distance_Km",
                "Items_Count", "Product_Category", "Payment_Method", "Customer_Rating", "Discount_Applied", "Delivery_Partner_Rating"]
        rows = []
        plats = list(PLATFORMS)
        for i in range(2400):
            p = r.choice(plats)
            dist = round(r.uniform(0.6, 7.5), 1)
            mins = max(4, round(r.gauss(PLATFORMS[p] + dist * 1.2, 4)))
            rows.append([str(5000001 + i), p, r.choice(CITIES), str(r.randint(18, 60)), str(r.randint(90, 2400)),
                         str(mins), str(dist), str(r.randint(1, 18)), r.choice(CATS), r.choice(PAY),
                         str(r.randint(1, 5)), str(r.randint(0, 1)), str(r.randint(1, 5))])
        return head, rows

    def build(self, recs):
        orders = []
        seen = set()
        for rec in self.sample(recs):
            oid = clean.parse_int(rec.get("order_id"))
            if oid is None or oid in seen:
                continue
            seen.add(oid)
            orders.append([oid, clean.fix_text(rec.get("platform")), clean.fix_text(rec.get("city")),
                           clean.parse_number(rec.get("order_value")), clean.parse_number(rec.get("delivery_min")),
                           clean.parse_number(rec.get("distance_km")), clean.parse_int(rec.get("items")),
                           clean.fix_text(rec.get("category")), clean.fix_text(rec.get("payment")),
                           clean.parse_number(rec.get("customer_rating")), clean.parse_bool(rec.get("discount")),
                           clean.parse_number(rec.get("partner_rating"))])
        for o in orders:                       # tidy floats from raw exports
            for j in (3, 4, 5, 9, 11):
                if o[j] is not None:
                    o[j] = round(o[j], 2)
        plats = sorted({o[1] for o in orders if o[1]})
        nxt = max(o[0] for o in orders) + 1
        # planted 1: 'teleporting' riders - long distance, impossible minutes
        for k in range(4):
            src = list(orders[(k + 1) * len(orders) // 6])
            src[0], src[4], src[5] = nxt, 3.0 + k, 9.5 + k
            orders.append(src)
            self.plant("orders", nxt, f"impossible delivery: {src[5]} km in {src[4]} min (> 100 km/h)")
            nxt += 1
        # planted 2: the same order id re-submitted (duplicate payout rows) -> kept in a separate payouts table
        payouts = [(o[0], round((o[3] or 0) * 0.08, 2)) for o in orders]
        dupes = [orders[len(orders) // 3][0], orders[len(orders) // 2][0], orders[(2 * len(orders)) // 3][0]]
        for d in dupes:
            payouts.append((d, next(p for o, p in payouts if o == d)))
            self.plant("rider_payouts", d, "rider payout claimed twice for the same order")
        payouts = [(i + 1, o, p) for i, (o, p) in enumerate(payouts)]
        promised = [(p, PLATFORMS.get(p, 15)) for p in plats]
        return [
            Table("orders", "One row per delivered quick-commerce order.", [
                Column("order_id", "INTEGER", "Order id", "PRIMARY KEY"),
                Column("platform", "TEXT", "Quick-commerce app", "REFERENCES platforms(platform)"),
                Column("city", "TEXT", "City"),
                Column("order_value", "REAL", "Order value in INR"),
                Column("delivery_min", "REAL", "Minutes from order to doorstep"),
                Column("distance_km", "REAL", "Dark store to customer distance (km)"),
                Column("items", "INTEGER", "Items in the basket"),
                Column("category", "TEXT", "Main product category"),
                Column("payment", "TEXT", "Payment method"),
                Column("customer_rating", "REAL", "Customer rating 1-5"),
                Column("discount", "INTEGER", "1 if a discount was applied"),
                Column("partner_rating", "REAL", "Delivery partner rating 1-5"),
            ], [tuple(o) for o in orders]),
            Table("platforms", "Delivery promise per platform (case configuration).", [
                Column("platform", "TEXT", "Platform name", "PRIMARY KEY"),
                Column("promised_min", "INTEGER", "Minutes promised in marketing"),
            ], promised),
            Table("rider_payouts", "Per-order incentive paid to delivery partners.", [
                Column("payout_id", "INTEGER", "Payout row id", "PRIMARY KEY"),
                Column("order_id", "INTEGER", "Order the payout is for", "REFERENCES orders(order_id)"),
                Column("amount", "REAL", "Payout in INR"),
            ], payouts),
        ]

    def case(self, tables):
        return {
            "title": "Dark Store Delivery Audit",
            "industry": "Quick Commerce",
            "tagline": "10-minute delivery, 4-minute riders and double payouts. Find out what the ops dashboard hides.",
            "client": "Ops finance team of a quick-commerce aggregator",
            "brief": [
                "Every app promises groceries in minutes. The ops dashboard says the promise is kept.",
                "Finance noticed rider incentives growing faster than orders, and a handful of deliveries that would need a "
                "rider moving faster than a train.",
                "Audit the order log, the delivery promises and the payout ledger.",
            ],
            "difficulty": "Intermediate",
            "accent": "purple",
        }

    def levels(self, tables):
        return [
            Level("Teleporting riders",
                  "Find orders whose implied speed is above 80 km/h (distance_km per delivery hour). "
                  "Return order_id, platform, speed_kmh rounded to 1 decimal.",
                  ["Speed = distance / time. delivery_min is minutes, so divide by 60.0 to get hours.",
                   "ROUND(distance_km / (delivery_min / 60.0), 1) and filter on the unrounded value in WHERE.",
                   "SELECT order_id, platform, ROUND(distance_km / (delivery_min / 60.0), 1) AS speed_kmh FROM orders "
                   "WHERE distance_km / (delivery_min / 60.0) > 80;"],
                  "SELECT order_id, platform, ROUND(distance_km / (delivery_min / 60.0), 1) AS speed_kmh FROM orders "
                  "WHERE delivery_min > 0 AND distance_km / (delivery_min / 60.0) > 80",
                  ["arithmetic", "ROUND", "WHERE"],
                  story="Nobody rides a scooter through city traffic at highway speed. These timestamps were edited."),
            Level("Promise vs reality",
                  "For each platform, what share of orders took longer than its promised_min? Return platform, orders, "
                  "late_pct (percentage, 1 decimal) - worst first, ties by platform.",
                  ["JOIN orders to platforms on platform.",
                   "AVG(CASE WHEN delivery_min > promised_min THEN 1.0 ELSE 0 END) * 100 gives a percentage.",
                   "SELECT o.platform, COUNT(*) AS orders, ROUND(100.0 * AVG(CASE WHEN o.delivery_min > p.promised_min THEN 1 ELSE 0 END), 1) "
                   "AS late_pct FROM orders o JOIN platforms p ON p.platform = o.platform GROUP BY o.platform ORDER BY late_pct DESC, o.platform;"],
                  "SELECT o.platform, COUNT(*) AS orders, ROUND(100.0 * AVG(CASE WHEN o.delivery_min > p.promised_min THEN 1 ELSE 0 END), 1) "
                  "AS late_pct FROM orders o JOIN platforms p ON p.platform = o.platform GROUP BY o.platform ORDER BY late_pct DESC, o.platform",
                  ["JOIN", "CASE WHEN", "conditional aggregation"], ordered=True,
                  story="Marketing says '10 minutes'. Let the data say how often that is true."),
            Level("Paid twice",
                  "Some orders received more than one rider payout. Return order_id, payouts, total_paid "
                  "(sum of amount, 2 decimals) for every such order.",
                  ["Group rider_payouts by order_id.",
                   "HAVING COUNT(*) > 1 keeps the duplicates.",
                   "SELECT order_id, COUNT(*) AS payouts, ROUND(SUM(amount), 2) AS total_paid FROM rider_payouts GROUP BY order_id HAVING COUNT(*) > 1;"],
                  "SELECT order_id, COUNT(*) AS payouts, ROUND(SUM(amount), 2) AS total_paid FROM rider_payouts GROUP BY order_id HAVING COUNT(*) > 1",
                  ["GROUP BY", "HAVING"],
                  story="Incentives are paid per order. Per order means once."),
            Level("Fastest app in every city",
                  "In each city, which platform has the lowest average delivery time? Only count platforms with at least "
                  "20 orders in that city and ignore orders with no city; ties by platform name. Return city, platform, avg_min (1 decimal) sorted by city.",
                  ["First aggregate per (city, platform) with HAVING COUNT(*) >= 20.",
                   "Then RANK or ROW_NUMBER() OVER (PARTITION BY city ORDER BY avg, platform) and keep rank 1.",
                   "WITH s AS (SELECT city, platform, AVG(delivery_min) AS a FROM orders WHERE city IS NOT NULL GROUP BY city, platform HAVING COUNT(*) >= 20), "
                   "r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY city ORDER BY a, platform) AS rn FROM s) "
                   "SELECT city, platform, ROUND(a, 1) AS avg_min FROM r WHERE rn = 1 ORDER BY city;"],
                  "WITH s AS (SELECT city, platform, AVG(delivery_min) AS a FROM orders WHERE city IS NOT NULL GROUP BY city, platform HAVING COUNT(*) >= 20), "
                  "r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY city ORDER BY a, platform) AS rn FROM s) "
                  "SELECT city, platform, ROUND(a, 1) AS avg_min FROM r WHERE rn = 1 ORDER BY city",
                  ["CTE", "window functions", "HAVING"], ordered=True,
                  story="The board wants one slide: who actually wins each city."),
        ]
