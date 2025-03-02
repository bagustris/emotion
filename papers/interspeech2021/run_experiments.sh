#!/usr/bin/env bash

# This script runs all the experiments from the Interspeech 2021 paper
# as well as additional experiments using "online" normalisation and
# proper inner cross-validation (with GridSearchCV).

# Only report TF internal errors (quite spammy otherwise)
export TF_CPP_MIN_LOG_LEVEL=2

all_corpora=(CaFE DEMoS EmoFilm IEMOCAP MSP-IMPROV Portuguese RAVDESS SAVEE ShEMO TESS URDU)
# all_corpora="ls features"
BASE_DIR="$(dirname "$0")"
SCRIPTS_DIR="$BASE_DIR/../../scripts"
EXP_SCRIPT="$SCRIPTS_DIR/training/class_cv.py"
DATASETS_DIR="$BASE_DIR/../../datasets"
FEATURES_DIR="$BASE_DIR/features"
RESULTS_DIR="$BASE_DIR/results"
CONF_DIR="$BASE_DIR/../../conf"


run_test() {
    local corpus="$1"; shift
    local features="$1"; shift
    local clf="$1"; shift
    local results_clf="$1"; shift
    local conf="$1"; shift
    local grid="$1"; shift
    echo "$corpus" "$features" "$clf" "$results_clf" "$conf" "$grid"

    local base_opts=(--features "$FEATURES_DIR/$corpus/$features.nc" --clf "$clf" --balanced --epochs 50 --learning_rate 0.0001)
    if [ -n "$conf" ]; then
        base_opts=("${base_opts[@]}" --clf_args "$conf")
    fi
    if [ -n "$grid" ]; then
        base_opts=("${base_opts[@]}" --param_grid "$grid")
    fi
    local common_opts
    local additional_opts

    # Experiments reported in paper
    common_opts=("${base_opts[@]}" --noinner_cv --results "$RESULTS_DIR/norm_offline/$corpus/$results_clf/$features.csv")
    case $corpus in
        CaFE|EMO-DB|JL|Portuguese|SAVEE|TESS)
            # Leave-one-speaker-out
            additional_opts=(--partition speaker --kfold -1 --normalise speaker);;
        CREMA-D|DEMoS|eNTERFACE|RAVDESS|ShEMO|SmartKom|VENEC)
            # Leave-one-speaker-group-out
            additional_opts=(--partition speaker --kfold 6 --normalise speaker);;
        IEMOCAP)
            # Leave-one-session-out
            additional_opts=(--partition session --map_groups "$CONF_DIR/mapping/iemocap_4class.yaml" --kfold -1 --normalise speaker);;
        MSP-IMPROV)
            # Leave-one-session-out
            additional_opts=(--partition session --kfold -1 --normalise speaker);;
        EmoFilm)
            # Leave-one-language-out
            additional_opts=(--partition language --kfold -1 --normalise language);;
        URDU)
            # Leave-one-speaker-out, use global normalisation
            additional_opts=(--partition speaker --kfold 6 --normalise all);;
    esac
    python "$EXP_SCRIPT" "$corpus_yaml" "${common_opts[@]}" "${additional_opts[@]}"

    # "Online" normalisation experiments with proper inner CV
    common_opts=("${base_opts[@]}" --normalise online --results "$RESULTS_DIR/norm_online/$corpus/$results_clf/$features.csv")
    case $corpus in
        CaFE|EMO-DB|JL|SAVEE)
            # Leave-one-speaker-out
            additional_opts=(--partition speaker --kfold -1 --inner_kfold 2);;
        TESS|Portuguese)
            # Leave-one-speaker-out
            additional_opts=(--partition speaker --kfold -1 --inner_kfold 2 --noinner_group);;
        CREMA-D|DEMoS|eNTERFACE|RAVDESS|ShEMO|SmartKom|URDU|VENEC)
            # Leave-one-speaker-group-out
            additional_opts=(--partition speaker --kfold 6 --inner_kfold 2);;
        IEMOCAP)
            # Leave-one-session-out
            additional_opts=(--partition session --map_groups "$CONF_DIR/mapping/iemocap_4class.yaml" --kfold -1 --inner_kfold 2);;
        MSP-IMPROV)
            # Leave-one-session-out
            additional_opts=(--partition session --kfold -1 --inner_kfold 2);;
        EmoFilm)
            # Leave-one-language-out
            additional_opts=(--partition language --kfold -1 --inner_kfold 2);;
    esac
    python "$EXP_SCRIPT" "$corpus_yaml" "${common_opts[@]}" "${additional_opts[@]}"
}


for corpus in "${all_corpora[@]}"; do
    corpus_yaml="$DATASETS_DIR/$corpus/corpus.yaml"
    for features in wav2vec wav2vec2 vq-wav2vec yamnet vggish densenet121 densenet169 densenet201; do
        for svm in linear poly2 poly3 rbf; do
            run_test "$corpus" $features sk/svm svm_$svm "$CONF_DIR/clf/sk/svm/$svm.yaml" "$CONF_DIR/clf/sk/svm/grids/$svm.yaml"
        done
        for mlp in 1layer 2layer 3layer; do
            run_test "$corpus" $features tf/mlp mlp_$mlp "$CONF_DIR/clf/tf/mlp/$mlp.yaml"
        done
        run_test "$corpus" $features tf/depinto2020 depinto2020
        run_test "$corpus" $features sk/rf rf "" "$CONF_DIR/clf/sk/rf/grids/default.yaml"
    done
done
