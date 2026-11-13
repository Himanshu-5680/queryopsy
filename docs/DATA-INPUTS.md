# Data inputs

Drop your CSV or XLSX exports into `data/raw/` and run `python -m pipeline.build`.
Files are matched by their headers (required columns must be present); the name patterns below break ties.
Header matching ignores case, spaces and punctuation, so `Amount in USD`, `amount_usd` and `AmountUSD` are the same.
If a dataset is missing, a clearly labelled synthetic placeholder is generated instead (`data/samples/`).

## Case 01 - `funding`

* Suggested file name: `data/raw/startup_funding.csv`
* Name patterns: `startup`, `funding`
* Designed for: [Indian Startup Funding (Kaggle: sudalairajkumar/indian-startup-funding)](https://www.kaggle.com/datasets/sudalairajkumar/indian-startup-funding) - licence: CC0: Public Domain
* Max rows kept (deterministic sample): 4,000

| Column (canonical) | Required | Accepted headers |
|---|---|---|
| `date` | yes | `Date dd/mm/yyyy`, `Date`, `deal date`, `funding date` |
| `startup` | yes | `Startup Name`, `startup`, `company`, `company name` |
| `vertical` |  | `Industry Vertical`, `industry`, `sector` |
| `subvertical` |  | `SubVertical`, `sub vertical` |
| `city` |  | `City  Location`, `City Location`, `city`, `location`, `hq` |
| `investors` |  | `Investors Name`, `investors`, `investor` |
| `round_type` |  | `InvestmentnType`, `Investment Type`, `InvestmentType`, `round`, `funding round`, `stage` |
| `amount` | yes | `Amount in USD`, `amount usd`, `amount`, `funding amount` |

## Case 02 - `quickcommerce`

* Suggested file name: `data/raw/quick_commerce.csv`, `data/raw/quick_commerce_data.csv`
* Name patterns: `quick`, `commerce`, `qcommerce`, `q_commerce`, `instamart`, `blinkit`
* Designed for: [Quick Commerce Dataset (Kaggle: rohitgrewal/quick-commerce-dataset) or any orders export with the same columns](https://www.kaggle.com/datasets/rohitgrewal/quick-commerce-dataset) - licence: ODbL (check the copy you use)
* Max rows kept (deterministic sample): 6,000

| Column (canonical) | Required | Accepted headers |
|---|---|---|
| `order_id` | yes | `Order_ID`, `order id`, `orderid` |
| `platform` | yes | `Company`, `platform`, `app`, `brand` |
| `city` | yes | `City` |
| `order_value` |  | `Order_Value`, `order value`, `order amount`, `amount`, `total` |
| `delivery_min` | yes | `Delivery_Time_Min`, `delivery time`, `delivery minutes`, `delivery_time` |
| `distance_km` | yes | `Distance_Km`, `distance` |
| `items` |  | `Items_Count`, `items`, `item count`, `quantity` |
| `category` |  | `Product_Category`, `category` |
| `payment` |  | `Payment_Method`, `payment`, `payment mode` |
| `customer_rating` |  | `Customer_Rating`, `rating` |
| `discount` |  | `Discount_Applied`, `discount` |
| `partner_rating` |  | `Delivery_Partner_Rating`, `partner rating`, `rider rating` |

## Case 03 - `catalog`

* Suggested file name: `data/raw/zepto_inventory.csv`, `data/raw/inventory.csv`, `data/raw/catalog.csv`
* Name patterns: `inventory`, `catalog`, `catalogue`, `zepto_v`, `product`
* Designed for: [Zepto Inventory Dataset (Kaggle: palvinder2006/zepto-inventory-dataset) or any catalogue export with the same columns](https://www.kaggle.com/datasets/palvinder2006/zepto-inventory-dataset) - licence: MIT
* Max rows kept (deterministic sample): 5,000

| Column (canonical) | Required | Accepted headers |
|---|---|---|
| `category` |  | `Category` |
| `name` | yes | `name`, `product`, `product name`, `title` |
| `mrp` | yes | `mrp`, `max retail price`, `Price_original`, `original price` |
| `discount_pct` |  | `discountPercent`, `discount percent`, `discount %`, `discount` |
| `available_qty` |  | `availableQuantity`, `available quantity`, `stock`, `stock qty`, `inventory` |
| `selling_price` | yes | `discountedSellingPrice`, `selling price`, `sale price`, `Price_discount`, `price` |
| `weight_g` |  | `weightInGms`, `weight`, `weight in gms`, `grams` |
| `out_of_stock` |  | `outOfStock`, `out of stock`, `oos` |
| `pack_qty` |  | `quantity`, `pack quantity`, `pack size`, `units` |

## Case 04 - `upi`

* Suggested file name: `data/raw/upi_transactions.csv`, `data/raw/upi_transactions_2024.csv`
* Name patterns: `upi`, `transaction`, `payment`
* Designed for: [UPI Transactions 2024 (Kaggle: skullagos5246/upi-transactions-2024-dataset; simulated by its author) or any export with the same columns](https://www.kaggle.com/datasets/skullagos5246/upi-transactions-2024-dataset) - licence: CC0: Public Domain
* Max rows kept (deterministic sample): 7,000

| Column (canonical) | Required | Accepted headers |
|---|---|---|
| `txn_id` |  | `transaction id`, `transaction_id`, `txn id`, `id` |
| `ts` | yes | `timestamp`, `datetime`, `date time`, `txn time`, `date` |
| `txn_type` |  | `transaction type`, `type` |
| `merchant_category` |  | `merchant_category`, `category` |
| `amount` | yes | `amount (INR)`, `amount`, `amount inr`, `value` |
| `status` |  | `transaction_status`, `status` |
| `sender_age` |  | `sender_age_group`, `age group` |
| `sender_state` |  | `sender_state`, `state` |
| `sender_bank` | yes | `sender_bank`, `payer bank`, `from bank` |
| `receiver_bank` | yes | `receiver_bank`, `payee bank`, `to bank` |
| `device` |  | `device_type`, `device` |
| `network` |  | `network_type`, `network` |
| `fraud_flag` | yes | `fraud_flag`, `is_fraud`, `fraud`, `label` |

## Case 05 - `payroll`

* Suggested file name: `data/raw/hr_employees.csv`, `data/raw/hr_attrition.csv`
* Name patterns: `hr`, `attrition`, `employee`, `payroll`
* Designed for: [HR Attrition data based on IBM attrition (Kaggle: singhnproud77/hr-attrition-dataset; IBM's fictional sample) or any HR export with the same columns](https://www.kaggle.com/datasets/singhnproud77/hr-attrition-dataset) - licence: CC0: Public Domain
* Max rows kept (deterministic sample): 2,000

| Column (canonical) | Required | Accepted headers |
|---|---|---|
| `emp_id` |  | `EmployeeNumber`, `employee id`, `emp id`, `employee_id` |
| `age` |  | `Age` |
| `department` | yes | `Department`, `dept` |
| `job_role` |  | `JobRole`, `job role`, `designation`, `role` |
| `job_level` |  | `JobLevel`, `job level`, `grade` |
| `monthly_income` | yes | `MonthlyIncome`, `monthly income`, `salary`, `monthly salary` |
| `overtime` |  | `OverTime`, `overtime` |
| `hire_date` |  | `Date_of_Hire`, `date of hire`, `hire date`, `joining date`, `doj` |
| `term_date` |  | `Date_of_termination`, `date of termination`, `termination date`, `exit date` |
| `attrition` |  | `Attrition` |
