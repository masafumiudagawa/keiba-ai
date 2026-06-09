export interface RaceInfo {
  name: string;
  date: string;
  venue: string;
  distance: number;
  surface: string;
  grade: string;
  post_time: string;
  track_condition: string;
  field_size: number;
}

export interface Factors {
  recent_form: number;
  course_aptitude: number;
  jockey_factor: number;
  public_opinion: number;
  training: number;
  g1_wins: number;
}

export interface Prediction {
  rank: number;
  horse_name: string;
  jockey: string | null;
  gate_number: number | null;
  post_position: number | null;
  age: number | null;
  sex: string | null;
  weight_carried: number | null;
  sire: string | null;
  prev_race: string | null;
  prev_finish: number | null;
  win_probability: number;
  place_probability: number;
  ai_score: number;
  mark: string;
  factors: Factors;
}

export interface PredictionResponse {
  race_info: RaceInfo;
  predictions: Prediction[];
}

export interface HorseRaceData {
  gate_number: number;
  horse_name: string;
  color: string;
  style: string;
  positions: number[];
  section_times: number[];
  finish_time: string;
  finish_position: number;
}

export interface SimulationResponse {
  summary: {
    num_simulations: number;
    win_counts: Record<string, number>;
    place_counts: Record<string, number>;
    avg_winning_time: string;
  };
  representative_race: {
    total_distance: number;
    checkpoints: number[];
    horses: HorseRaceData[];
    pace: { first_1000m: string; last_600m: string; type: string };
  };
}

export interface BetRecommendation {
  bet_type: string;
  bet_type_ja: string;
  selection: string;
  amount: number;
  odds: number;
  hit_prob: number;
  expected_value: number;
  kelly_fraction: number;
}

export interface BettingResponse {
  recommendations: BetRecommendation[];
  total_budget: number;
  expected_return: number;
  expected_roi: number;
  risk_metrics: { worst_case: number; best_case: number };
}
