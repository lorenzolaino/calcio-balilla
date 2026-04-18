import unittest
from unittest.mock import MagicMock, patch, Mock
import sys
import os
import random

# Mock Streamlit and setup environment
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
mock_st = Mock()
sys.modules['streamlit'] = mock_st

from models import DatabaseManager

class TestSeasonSimulation(unittest.TestCase):

    @patch('models.engine')
    def test_mini_season_simulation(self, mock_engine):
        """Simulates 100 matches to see if the leaderboard stabilizes logically."""
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn

        # 10 Players with different "internal skills"
        # We'll see if the ratings eventually reflect these skills
        player_skills = {
            f"Player_{i}": i * 100 for i in range(10) # Skill from 0 to 900
        }
        
        # In-memory database simulation
        class PlayerRow:
            def __init__(self, data):
                self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff, self.trend = data
            def __getitem__(self, i):
                return [self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff, self.trend][i]
            def __iter__(self):
                return iter([self.id, self.name, self.rating, self.games, self.wins, self.losses, self.goal_diff, self.trend])

        db_players = {
            name: [i, name, 1000.0, 0, 0, 0, 0, ""] 
            for i, name in enumerate(player_skills.keys())
        }

        def mock_execute(stmt, params=None):
            stmt_text = str(stmt).lower()
            
            if "select max(rating), min(rating)" in stmt_text:
                ratings = [p[2] for p in db_players.values()]
                res = MagicMock()
                res.fetchone.return_value = (max(ratings), min(ratings))
                return res
            
            if "select id, name, rating" in stmt_text:
                names = params['names']
                res = MagicMock()
                res.fetchall.return_value = [PlayerRow(db_players[n]) for n in names]
                return res
            
            if "update players" in stmt_text:
                # params is a list of dicts: [{'r':..., 'id':...}, ...]
                for p_update in params:
                    p_id = p_update['id']
                    # Find player by id
                    for p_name, p_data in db_players.items():
                        if p_data[0] == p_id:
                            p_data[2] = p_update['r']
                            p_data[3] = p_update['g']
                            p_data[4] = p_update['w']
                            p_data[5] = p_update['l']
                            p_data[6] = p_update['gd']
                            p_data[7] = p_update['t']
                return MagicMock()

            if "insert into matches" in stmt_text:
                res = MagicMock()
                res.scalar.return_value = random.randint(1, 1000)
                return res
            
            return MagicMock()

        mock_conn.execute.side_effect = mock_execute

        # Run 300 matches for better convergence
        player_names = list(player_skills.keys())
        for _ in range(300):
            # Pick 4 random players
            match_players = random.sample(player_names, 4)
            a1, a2, b1, b2 = match_players
            
            # Predict winner based on internal skill (using 400 scale like Elo)
            skill_a = (player_skills[a1] + player_skills[a2]) / 2.0
            skill_b = (player_skills[b1] + player_skills[b2]) / 2.0
            
            # Probability of A winning
            prob_a = 1.0 / (1.0 + 10 ** ((skill_b - skill_a) / 400.0))
            
            if random.random() < prob_a:
                # Team A wins
                goals_a, goals_b = 10, random.randint(0, 8)
            else:
                # Team B wins
                goals_a, goals_b = random.randint(0, 8), 10
            
            DatabaseManager.record_match(a1, a2, b1, b2, goals_a, goals_b)

        # Final Leaderboard Analysis
        sorted_players = sorted(db_players.values(), key=lambda x: x[2], reverse=True)
        
        print("\n--- Final Simulated Leaderboard (300 matches) ---")
        for p in sorted_players:
            skill = player_skills[p[1]]
            print(f"Name: {p[1]}, Rating: {p[2]:.1f}, Games: {p[3]}, Skill: {skill}")

        # Verification 1: Correlation between skill and rating
        # The top 3 should be from the top 5 skilled players
        top_3_names = [p[1] for p in sorted_players[:3]]
        top_5_skilled = [f"Player_{i}" for i in range(5, 10)]
        matches = len(set(top_3_names) & set(top_5_skilled))
        self.assertTrue(matches >= 2, f"Only {matches} of top 3 players are in the top 5 skilled group")
        
        # Verification 2: Average rating stability
        avg_rating = sum(p[2] for p in db_players.values()) / len(db_players)
        print(f"Average Rating: {avg_rating:.1f}")
        # Inflation is expected but should be controlled
        self.assertTrue(950 < avg_rating < 1100)

if __name__ == '__main__':
    unittest.main()
