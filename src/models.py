from dataclasses import dataclass
import datetime

@dataclass
class Person:
    name: str
    email: str
    skills: list[str]
    associates: list[str]
    homeworld: str
    created_at: datetime
    matching_skills: int = 0
    jumps_from_base: int = 0
    avg_associate_affinity: float = 0.0
    ranking_score: float = 0.0

@dataclass
class System:
    name: str
    x: float
    y: float
    region: str
    type: str = 'System'
    importance: float = 0.0
    rebel_affinity: float = 0.5