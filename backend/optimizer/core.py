from ortools.linear_solver import pywraplp
import pandas as pd
from typing import List, Dict, Any

class DFSOptimizer:
    def __init__(self, projections: pd.DataFrame, settings: Dict[str, Any]):
        """
        projections: DataFrame containing ['id', 'name', 'salary', 'projected_fp', 'roster_position', 'team']
        settings: {
            'num_lineups': int,
            'min_uniqueness': int,
            'max_exposure': float,
            'locked': List[int],
            'excluded': List[int]
        }
        """
        self.df = projections.copy()
        self.settings = settings
        self.solver = pywraplp.Solver.CreateSolver('SCIP') # SCIP is an excellent integer programming solver
        
        # Internal states
        self.player_vars = {}
        self.lineups_generated = []

    def build_variables(self):
        # Create binary variable for each player: 1 if selected, 0 otherwise
        for idx, row in self.df.iterrows():
            if row['id'] in self.settings.get('excluded', []):
                continue # Exclude player completely
            
            # Lower bound 1 if locked, 0 otherwise
            lb = 1 if row['id'] in self.settings.get('locked', []) else 0
            self.player_vars[idx] = self.solver.IntVar(lb, 1, f"player_{idx}")

    def build_nba_draftkings_constraints(self):
        # Cap: <= $50,000
        salary_constraint = self.solver.Constraint(0, 50000, "salary")
        # Lineup size: exactly 8 players
        size_constraint = self.solver.Constraint(8, 8, "lineup_size")

        for idx, var in self.player_vars.items():
            salary_constraint.SetCoefficient(var, int(self.df.loc[idx, 'salary']))
            size_constraint.SetCoefficient(var, 1)

        # Positions: PG, SG, SF, PF, C, G, F, UTIL
        # Mapping standard positions to DraftKings slots
        # We need flexible position mapping. A PG can be PG, G, UTIL
        # We'll use a simplified positional constraint system:
        # At least 1 PG, 1 SG, 1 SF, 1 PF, 1 C.
        # This handles the strict requirements. The rest fall into G/F/UTIL naturally if size=8.
        
        pos_constraints = {
            'PG': self.solver.Constraint(1, 3, "PG_req"),
            'SG': self.solver.Constraint(1, 3, "SG_req"),
            'SF': self.solver.Constraint(1, 3, "SF_req"),
            'PF': self.solver.Constraint(1, 3, "PF_req"),
            'C': self.solver.Constraint(1, 2, "C_req"),
        }

        # Guards (PG/SG) total between 3 and 4 (G flex)
        guard_limit = self.solver.Constraint(3, 4, "Guard_req")
        # Forwards (SF/PF) total between 3 and 4 (F flex)
        forward_limit = self.solver.Constraint(3, 4, "Forward_req")

        for idx, var in self.player_vars.items():
            pos_str = str(self.df.loc[idx, 'roster_position']).upper()
            if 'PG' in pos_str:
                pos_constraints['PG'].SetCoefficient(var, 1)
                guard_limit.SetCoefficient(var, 1)
            elif 'SG' in pos_str:
                pos_constraints['SG'].SetCoefficient(var, 1)
                guard_limit.SetCoefficient(var, 1)
            elif 'SF' in pos_str:
                pos_constraints['SF'].SetCoefficient(var, 1)
                forward_limit.SetCoefficient(var, 1)
            elif 'PF' in pos_str:
                pos_constraints['PF'].SetCoefficient(var, 1)
                forward_limit.SetCoefficient(var, 1)
            elif 'C' in pos_str:
                pos_constraints['C'].SetCoefficient(var, 1)

    def optimize_lineup(self):
        objective = self.solver.Objective()
        for idx, var in self.player_vars.items():
            objective.SetCoefficient(var, float(self.df.loc[idx, 'projected_fp']))
        objective.SetMaximization()

        status = self.solver.Solve()
        if status == pywraplp.Solver.OPTIMAL:
            lineup_indices = [idx for idx, var in self.player_vars.items() if var.solution_value() > 0.5]
            return lineup_indices
        return None

    def add_uniqueness_constraint(self, previous_lineup_indices: List[int], min_uniqueness: int):
        # Sum of variables in the previous lineup must be <= (Lineup Size - min_uniqueness)
        # For NBA DK size=8.
        max_overlap = 8 - min_uniqueness
        overlap_constraint = self.solver.Constraint(0, max_overlap, f"uniqueness_{len(self.lineups_generated)}")
        for idx in previous_lineup_indices:
            if idx in self.player_vars:
                overlap_constraint.SetCoefficient(self.player_vars[idx], 1)

    def generate(self):
        self.build_variables()
        self.build_nba_draftkings_constraints()
        
        num_lineups = self.settings.get('num_lineups', 1)
        min_uniqueness = self.settings.get('min_uniqueness', 2)

        results = []
        for i in range(num_lineups):
            lineup_indices = self.optimize_lineup()
            if not lineup_indices:
                break # Infeasible
            
            # Store lineup
            score = sum(self.df.loc[idx, 'projected_fp'] for idx in lineup_indices)
            salary = sum(self.df.loc[idx, 'salary'] for idx in lineup_indices)
            players = self.df.loc[lineup_indices].to_dict('records')
            self.lineups_generated.append(lineup_indices)
            
            results.append({
                'lineup_id': i + 1,
                'projected_score': score,
                'salary': salary,
                'players': players
            })

            # Prevent this exact lineup structure with overlap rules
            self.add_uniqueness_constraint(lineup_indices, min_uniqueness)
            
        return results
