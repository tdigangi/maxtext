echo "Running 8b.sh"
# 8B parameter model inference.
# This config will work out of the box for a single CPU VM.
#
# Command Flags:
# OUTPUT_PATH (Required, unless base_output_directory is already set in base.yml)
# DATASET_PATH (Required, unless dataset_path is already set in base.yml)
# RUN_NAME (Required, unless run_name is already set in base.yml)
#
# Example to invoke this script:
# bash MaxText/configs/cpu/8b.sh RUN_NAME="<your_run_name>" OUTPUT_PATH="gs://<your_output_path>" DATASET_PATH="gs://<your_dataset_path>"


# Stop execution if any command exits with error
set -e

# Set environment variables
for ARGUMENT in "$@"; do
    IFS='=' read -r KEY VALUE <<< "$ARGUMENT"
    export "$KEY"="$VALUE"
done

# Decode
python3 MaxText/decode.py MaxText/configs/base.yml run_name=$RUN_NAME\
    per_device_batch_size=1 enable_checkpointing=false\
    enable_profiler=false global_parameter_scale=8\
    max_target_length=128 base_output_directory=$OUTPUT_PATH\
    dataset_path=$DATASET_PATH attention='dot_product' add_eos=false\