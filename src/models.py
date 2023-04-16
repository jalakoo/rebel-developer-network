from dataclasses import dataclass

@dataclass
class Person:
    name: str
    email: str
    skills: list[str]
    associates: list[str]
    homeworld: str