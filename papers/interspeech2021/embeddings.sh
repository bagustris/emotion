#!/usr/bin/env bash

# This script extracts neural embeddings for all corpora
# to be run from "emotion" root directory
export TF_CPP_MIN_LOG_LEVEL=1

# Change this for VGGish/YAMNet as required depending on GPU memory
batch_size=${batch_size:=16}  # default: 256

# Change to correct wav2vec models dir
#wav2vec_models_dir=${wav2vec_models_dir:=$HOME/src/fairseq/examples/wav2vec}
script_dir=$(dirname "$0")
wav2vec_models_dir="$script_dir/../../third_party"
# wav2vec_models_dir = "$script_dir/third_party"

for corpus in CaFE DEMoS EmoFilm IEMOCAP MSP-IMPROV Portuguese RAVDESS SAVEE ShEMO TESS URDU; do
    # # auDeep dataset conversion
    # if [ -f "features/$corpus/audeep.nc" ]; then
    #     python scripts/utils/convert_audeep_dataset.py \
    #         features/$corpus/audeep.nc \
    #         $corpus
    # else
    #     echo "auDeep file not found for $corpus"
    # fi

    # # DeepSpectrum dataset conversion
    # for net in densenet201 densenet169 densenet121; do
    #     if [ -f "features/$corpus/$net.csv" ]; then
    #         python /scripts/utils/convert.py \
    #             features/$corpus/$net.csv \
    #             features/$corpus/$net.nc \
    #             --corpus $corpus
    #         rm features/$corpus/$net.csv
    #     fi
    # done

    # # Spectrograms
    # python ../../scripts/preprocessing/spectrograms.py \
    #     $corpus \
    #     ../../datasets/$corpus/files_all.txt \
    #     --window_size 0.025 \
    #     --window_shift 0.01 \
    #     --mel_bands 64 \
    #     --fmin 125 \
    #     --fmax 7500 \
    #     --output features/$corpus/spectrograms-0.025-0.010-64.nc

    # YAMNet and VGGish mean embeddings
    python ../../scripts/preprocessing/yamnet_features.py \
        --yamnet "$wav2vec_models_dir/models/audioset/yamnet/" \
        features/$corpus/spectrograms-0.025-0.010-64.nc \
        features/$corpus/yamnet.nc \
        --batch_size $batch_size
    python ../../scripts/preprocessing/vggish_features.py \
        --vggish "$wav2vec_models_dir/models/audioset/vggish/" \
        features/$corpus/spectrograms-0.025-0.010-64.nc \
        features/$corpus/vggish.nc \
        --batch_size $batch_size

    # (VQ-)Wav2Vec mean embeddings
    python ../../scripts/preprocessing/wav2vec_features.py \
        --checkpoint "$wav2vec_models_dir/wav2vec_large.pt" \
        --type 1 \
        --corpus $corpus \
        ../../datasets/$corpus/files_all.txt \
        features/$corpus/wav2vec.nc
    python ../../scripts/preprocessing/wav2vec_features.py \
        --checkpoint "$wav2vec_models_dir/vq-wav2vec.pt" \
        --type 1 \
        --corpus $corpus \
        ../../datasets/$corpus/files_all.txt \
        features/$corpus/vq-wav2vec.nc
    # Wav2Vec 2.0
    python ../../scripts/preprocessing/wav2vec_features.py \
        --checkpoint "$wav2vec_models_dir/libri960_big.pt" \
        --type 2 \
        --corpus $corpus \
        ../../datasets/$corpus/files_all.txt \
        features/$corpus/wav2vec2.nc
done
