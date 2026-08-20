from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from pandas.api.types import is_numeric_dtype
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PROJECT_DIR = Path(__file__).resolve().parent
DATA_PATH = PROJECT_DIR / "data" / "processed" / "earthquake_rf_recovery_dataset.csv"
FEATURE_PATH = PROJECT_DIR / "data" / "processed" / "earthquake_rf_feature_columns.txt"
TARGET_COLUMN = "recovery_cycle_years"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "outputs" / "random_forest_recovery"


def read_feature_columns(feature_path: Path, df: pd.DataFrame) -> list[str]:
    features = [
        line.strip()
        for line in feature_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    missing = [feature for feature in features if feature not in df.columns]
    if missing:
        raise ValueError(f"Feature columns are missing from dataset: {missing}")
    return features


def split_feature_types(df: pd.DataFrame, features: list[str]) -> tuple[list[str], list[str]]:
    numeric_features = [column for column in features if is_numeric_dtype(df[column])]
    categorical_features = [column for column in features if column not in numeric_features]
    return numeric_features, categorical_features


def build_model(
    numeric_features: list[str],
    categorical_features: list[str],
    n_estimators: int,
    max_depth: int | None,
    random_state: int,
    n_jobs: int,
) -> Pipeline:
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ]
    )
    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features),
        ]
    )
    classifier = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=3,
        class_weight="balanced_subsample",
        random_state=random_state,
        n_jobs=n_jobs,
    )
    return Pipeline(
        steps=[
            ("preprocess", preprocessor),
            ("model", classifier),
        ]
    )


def parse_tree_depth(value: str) -> int | None:
    if value.lower() in {"none", "null"}:
        return None
    return int(value)


def clean_encoded_feature_name(encoded_name: str, categorical_features: list[str]) -> str:
    if encoded_name.startswith("num__"):
        return encoded_name.replace("num__", "", 1)
    if encoded_name.startswith("cat__"):
        remainder = encoded_name.replace("cat__", "", 1)
        for feature in sorted(categorical_features, key=len, reverse=True):
            if remainder == feature or remainder.startswith(f"{feature}_"):
                return feature
        return remainder
    return encoded_name


def extract_feature_importance(
    model: Pipeline,
    categorical_features: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    preprocessor = model.named_steps["preprocess"]
    forest = model.named_steps["model"]
    encoded_names = preprocessor.get_feature_names_out()
    encoded_importance = pd.DataFrame(
        {
            "encoded_feature": encoded_names,
            "importance": forest.feature_importances_,
        }
    ).sort_values("importance", ascending=False)
    encoded_importance["original_feature"] = encoded_importance["encoded_feature"].map(
        lambda name: clean_encoded_feature_name(name, categorical_features)
    )
    original_importance = (
        encoded_importance.groupby("original_feature", as_index=False)["importance"]
        .sum()
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    return encoded_importance, original_importance


def save_confusion_matrix_plot(
    y_true: pd.Series,
    y_pred: pd.Series,
    labels: list[int],
    output_path: Path,
) -> None:
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    fig, ax = plt.subplots(figsize=(7, 6))
    image = ax.imshow(matrix, interpolation="nearest", cmap="Blues")
    fig.colorbar(image, ax=ax)
    ax.set_title("Random Forest Confusion Matrix")
    ax.set_xlabel("Predicted recovery cycle")
    ax.set_ylabel("Actual recovery cycle")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    threshold = matrix.max() / 2 if matrix.size else 0
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            color = "white" if matrix[row, col] > threshold else "black"
            ax.text(col, row, matrix[row, col], ha="center", va="center", color=color)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_feature_importance_plot(importance: pd.DataFrame, output_path: Path, top_n: int) -> None:
    top = importance.head(top_n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.barh(top["original_feature"], top["importance"], color="#3b6ea8")
    ax.set_title(f"Top {top_n} Feature Importances")
    ax.set_xlabel("Importance")
    ax.set_ylabel("Feature")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_target_distribution_plot(df: pd.DataFrame, output_path: Path) -> None:
    counts = df[TARGET_COLUMN].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(counts.index.astype(str), counts.values, color="#5a8f5a")
    ax.set_title("Recovery Cycle Target Distribution")
    ax.set_xlabel("Recovery cycle years")
    ax.set_ylabel("Sample count")
    for index, value in enumerate(counts.values):
        ax.text(index, value, str(value), ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_predictions(
    df: pd.DataFrame,
    test_index: pd.Index,
    y_true: pd.Series,
    y_pred: pd.Series,
    probabilities,
    classes: list[int],
    output_path: Path,
) -> None:
    predictions = df.loc[test_index, ["sample_id", "usgs_event_id", "event_date", "area", "year"]].copy()
    predictions["actual_recovery_cycle_years"] = y_true.to_numpy()
    predictions["predicted_recovery_cycle_years"] = y_pred
    for index, class_label in enumerate(classes):
        predictions[f"prob_class_{class_label}"] = probabilities[:, index]
    predictions.to_csv(output_path, index=False, encoding="utf-8-sig")


def grouped_train_test_split(
    x: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    test_size: float,
    random_state: int,
    max_attempts: int = 200,
):
    labels = set(y.unique())
    last_split = None
    last_seed = random_state
    for offset in range(max_attempts):
        seed = random_state + offset
        splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
        train_index, test_index = next(splitter.split(x, y, groups=groups))
        last_split = (train_index, test_index)
        last_seed = seed
        if set(y.iloc[train_index].unique()) == labels and set(y.iloc[test_index].unique()) == labels:
            return train_index, test_index, seed
    train_index, test_index = last_split
    return train_index, test_index, last_seed


def train_and_evaluate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.data_path)
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Target column `{TARGET_COLUMN}` is missing from dataset.")

    features = read_feature_columns(Path(args.feature_path), df)
    numeric_features, categorical_features = split_feature_types(df, features)

    x = df[features]
    y = df[TARGET_COLUMN].astype(int)
    if args.split_method == "group":
        groups = df["area"].astype(str) + "_" + df["year"].astype(int).astype(str)
        train_index, test_index, split_random_state = grouped_train_test_split(
            x=x,
            y=y,
            groups=groups,
            test_size=args.test_size,
            random_state=args.random_state,
        )
        x_train = x.iloc[train_index]
        x_test = x.iloc[test_index]
        y_train = y.iloc[train_index]
        y_test = y.iloc[test_index]
    else:
        x_train, x_test, y_train, y_test = train_test_split(
            x,
            y,
            test_size=args.test_size,
            random_state=args.random_state,
            stratify=y,
        )
        split_random_state = args.random_state

    model = build_model(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        n_estimators=args.n_estimators,
        max_depth=parse_tree_depth(args.max_depth),
        random_state=args.random_state,
        n_jobs=args.n_jobs,
    )
    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)
    probabilities = model.predict_proba(x_test)
    labels = sorted(y.unique().tolist())

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
        "macro_f1": float(f1_score(y_test, y_pred, average="macro")),
        "weighted_f1": float(f1_score(y_test, y_pred, average="weighted")),
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "target_column": TARGET_COLUMN,
        "feature_count": int(len(features)),
        "numeric_feature_count": int(len(numeric_features)),
        "categorical_feature_count": int(len(categorical_features)),
        "n_estimators": int(args.n_estimators),
        "max_depth": args.max_depth,
        "random_state": int(args.random_state),
        "split_random_state": int(split_random_state),
        "n_jobs": int(args.n_jobs),
        "test_size": float(args.test_size),
        "split_method": args.split_method,
        "class_labels": labels,
    }
    report_dict = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    report_text = classification_report(y_test, y_pred, zero_division=0)

    (output_dir / "metrics.json").write_text(
        json.dumps({"metrics": metrics, "classification_report": report_dict}, indent=2),
        encoding="utf-8",
    )
    (output_dir / "classification_report.txt").write_text(report_text, encoding="utf-8")

    encoded_importance, original_importance = extract_feature_importance(model, categorical_features)
    encoded_importance.to_csv(output_dir / "feature_importance_encoded.csv", index=False, encoding="utf-8-sig")
    original_importance.to_csv(output_dir / "feature_importance.csv", index=False, encoding="utf-8-sig")

    save_confusion_matrix_plot(y_test, y_pred, labels, output_dir / "confusion_matrix.png")
    save_feature_importance_plot(original_importance, output_dir / "feature_importance_top20.png", top_n=20)
    save_target_distribution_plot(df, output_dir / "target_distribution.png")
    save_predictions(
        df=df,
        test_index=x_test.index,
        y_true=y_test,
        y_pred=y_pred,
        probabilities=probabilities,
        classes=labels,
        output_path=output_dir / "test_predictions.csv",
    )
    joblib.dump(model, output_dir / "random_forest_recovery_model.joblib")

    print("Random forest training finished.")
    print(f"Output directory: {output_dir}")
    print(json.dumps(metrics, indent=2))
    print("\nTop 10 original feature importances:")
    print(original_importance.head(10).to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a random forest model for post-earthquake economic recovery cycle prediction."
    )
    parser.add_argument("--data-path", default=str(DATA_PATH))
    parser.add_argument("--feature-path", default=str(FEATURE_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-estimators", type=int, default=500)
    parser.add_argument("--max-depth", default="None")
    parser.add_argument("--n-jobs", type=int, default=1)
    parser.add_argument(
        "--split-method",
        choices=["group", "stratified"],
        default="group",
        help="group keeps the same area-year out of both train and test to reduce leakage.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    train_and_evaluate(parse_args())
