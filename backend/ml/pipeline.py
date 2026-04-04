import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import pandas as pd
import numpy as np

class XGBoostProjectionModel:
    def __init__(self, target_col='fantasy_points'):
        self.model = xgb.XGBRegressor(
            objective='reg:squarederror',
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            subsample=0.8,
            colsample_bytree=0.8
        )
        self.target_col = target_col

    def preprocess(self, df: pd.DataFrame):
        """
        Handle missing values and one-hot encoding for categorical variables.
        Expected feature columns: 'minutes', 'usage', 'pace', 'implied_team_total', 'opp_def_rank'
        """
        # Fill missing numeric
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        df[num_cols] = df[num_cols].fillna(0)

        # Drop non-feature columns
        drop_cols = [self.target_col, 'id', 'player_id', 'date', 'name', 'team', 'roster_position']
        drop_cols = [c for c in drop_cols if c in df.columns]
        
        X = df.drop(columns=drop_cols)
        y = df[self.target_col] if self.target_col in df.columns else None

        # Convert categories to one-hot if any
        X = pd.get_dummies(X, drop_first=True)
        return X, y

    def train_model(self, historical_data: pd.DataFrame):
        """
        Train XGBoost Regressor on historical data comparing matched features to ACTUAL fantasy points.
        """
        X, y = self.preprocess(historical_data)
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )

        predictions = self.model.predict(X_test)
        mae = mean_absolute_error(y_test, predictions)
        rmse = np.sqrt(mean_squared_error(y_test, predictions))
        
        return {
            "mae": float(mae),
            "rmse": float(rmse),
            "status": "success"
        }

    def predict(self, current_slate_features: pd.DataFrame):
        X, _ = self.preprocess(current_slate_features)
        
        # Ensure columns match training
        missing_cols = set(self.model.feature_names_in_) - set(X.columns)
        for c in missing_cols:
            X[c] = 0
        X = X[self.model.feature_names_in_]

        preds = self.model.predict(X)
        current_slate_features['projected_fp'] = preds
        return current_slate_features
