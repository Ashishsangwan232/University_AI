import math


def percentage(attended: int, total: int) -> float:
    return round(attended / total * 100, 1) if total else 0.0


def calculate(attended: int, total: int, target: float) -> dict:
    current = percentage(attended, total)

    if total == 0:
        return {
            "current_percentage": current,
            "target_percentage": target,
            "can_miss": 0,
            "must_attend": 0,
        }

    # Find the largest x such that attended / (total + x) >= target / 100.
    if current >= target:
        can_miss = math.floor((attended * 100 / target) - total)
        can_miss = max(0, can_miss)
        must_attend = 0
    else:
        # Find the smallest x such that (attended + x)/(total + x) >= target/100.
        required = (target * total - 100 * attended) / (100 - target)
        can_miss = 0
        must_attend = max(0, math.ceil(required))

    return {
        "current_percentage": current,
        "target_percentage": target,
        "can_miss": can_miss,
        "must_attend": must_attend,
    }
