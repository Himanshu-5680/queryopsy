"""Fictional name generators for placeholder data (never real companies or people)."""
import random

SYL = ["kira", "paisa", "zip", "nova", "lumo", "veda", "tara", "orbi", "kosh", "mitra", "ruta", "sona",
       "dhan", "pixi", "yatra", "vyom", "neer", "agni", "kalp", "moksh", "arth", "setu", "chala", "deep"]
SUF = ["ly", "go", "hub", "labs", "box", "kart", "pay", "verse", "mint", "nest", "wala", "x"]
FIRST = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Ishita", "Vihaan", "Anaya", "Arjun", "Sara", "Dev", "Nisha",
         "Kunal", "Pooja", "Rahul", "Tanvi", "Yash", "Zoya", "Aditya", "Riya", "Farhan", "Lata", "Manav", "Priya"]
LAST = ["Sharma", "Iyer", "Khan", "Reddy", "Das", "Patel", "Nair", "Gupta", "Singh", "Mehta", "Rao", "Bose",
        "Kulkarni", "Chopra", "Menon", "Joshi", "Verma", "Pillai", "Ghosh", "Saxena"]
FUND_A = ["Banyan", "Monsoon", "Saffron", "Deccan", "Peacock", "Indigo", "Lotus", "Himalaya", "Coral", "Tusker"]
FUND_B = ["Peak Ventures", "Capital", "Growth Partners", "Seed Fund", "Angels", "Equity", "Venture Partners"]


def startup(rng: random.Random) -> str:
    return (rng.choice(SYL) + rng.choice(SYL[::-1]) + rng.choice(SUF)).capitalize()


def person(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def fund(rng: random.Random) -> str:
    return f"{rng.choice(FUND_A)} {rng.choice(FUND_B)}"
