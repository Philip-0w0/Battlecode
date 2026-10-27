"""Bounded progress tracking; movement alone never counts as productivity."""

class Progress:
    def __init__(self):
        self.reset()

    def reset(self):
        self.goal = None
        self.best = None
        self.last_change = None
        self.last_round = None
        self.idle = 0
        self.positions = []

    def observe(self, round_number, goal, position, distance, resources):
        if self.last_round is not None and round_number != self.last_round + 1:
            self.reset()
        changed = (self.last_change is None or resources[:3] != self.last_change[:3]
                   or (goal == self.goal and resources[3] is not None
                       and self.last_change[3] is not None and resources[3] < self.last_change[3]))
        if goal != self.goal:
            self.best = distance
        closer = self.best is None or distance < self.best
        self.idle = 0 if changed or closer else self.idle + 1
        self.goal, self.last_change, self.last_round = goal, resources, round_number
        self.best = distance if self.best is None else min(self.best, distance)
        self.positions = (self.positions + [position])[-6:]
        cycle = (len(self.positions) == 6 and len(set(self.positions)) <= 2)
        return self.idle >= 18 or (cycle and self.idle >= 6)
